use strict;
use warnings;
use utf8;
use Encode qw(decode FB_CROAK);
use JSON::PP;
use File::Glob qw(bsd_glob);

# Run from the repository root, after extracting the original assets and
# decoding the corresponding official DCP deltas into analisis/ingles.
# This script only reads assets and writes inventories; it never reinserts text.
binmode STDOUT, ':encoding(UTF-8)';
sub load {
    open my $f, '<:raw', $_[0] or die "$_[0]: $!";
    local $/;
    return <$f>;
}
sub csv {
    my ($path, $header, $rows) = @_;
    open my $f, '>:encoding(UTF-8)', $path or die $!;
    print $f "\x{FEFF}";
    for my $row ($header, @$rows) {
        print $f join(',', map { my $s = defined $_ ? "$_" : ''; $s =~ s/"/""/g; '"'.$s.'"' } @$row), "\n";
    }
}
sub strings {
    my ($data, $start, $end) = @_;
    die 'Invalid string area' unless $end > $start && $end <= length $data;
    my @out;
    my $p = $start;
    while ($p < $end) {
        $p++ while $p < $end && substr($data, $p, 1) eq "\0";
        last if $p == $end;
        my $z = index($data, "\0", $p);
        die 'Unterminated string' if $z < 0 || $z >= $end;
        my $raw = substr($data, $p, $z - $p);
        my $text = decode('shiftjis', $raw, FB_CROAK);
        push @out, {offset => $p, text => $text};
        $p = $z + 1;
    }
    return \@out;
}
sub message_strings {
    my ($name, $original) = @_;
    my $data = load('analisis/'.($original ? 'original/' : 'ingles/').$name);
    # The unchanged pointer-table tail lengths come from the upstream inserters.
    my $win = $name =~ /WIN/;
    my $end = unpack('V', substr($data, 0, 4)) - ($win ? 58784 : 2016);
    return strings($data, $win ? 5108 : 260, $end);
}

my $exe = load('analisis/ingles/1ST_READ.BIN');
my @moves;
my %seen;
# The English move list is relocated by insert_moves.pl to 0x1A5260.
my $moves = substr($exe, 1725024, 12032);
while ($moves =~ /\xFF([^\xFF]+)\xFF/g) {
    my $chunk = $1;
    while ($chunk =~ /([A-Za-z][A-Za-z0-9 '.,()+\/-]{2,})/g) {
        my $term = $1;
        $term =~ s/^\s+|\s+$//g;
        next if $seen{$term}++;
        push @moves, [$term, 'CONSERVAR_EN_INGLES', 'Lista de comandos; extracción preliminar, puede incluir condiciones de ejecución'];
    }
}
csv('analisis/terminos-comandos.csv', [qw(texto accion observacion)], \@moves);
my @terms = sort {length($b) <=> length($a)} map {$_->[0]} @moves;
push @terms, 'SAFE FALL', 'EX.GROOVE', 'RATIO', 'VS Mode', 'Bonus Mode',
    'Millionaire Fighting Tournament', 'Capcom vs. SNK 2', 'Start', 'A+B+X+Y';
sub protected_terms {
    my ($s) = @_;
    return join(' | ', grep {length($_) >= 5 && index(lc($s), lc($_)) >= 0} @terms);
}

my $ja = message_strings('MESJ_WIN.BIN', 1);
my $a = message_strings('MESJ_WIN.BIN', 0);
my $b = message_strings('MESE_WIN.BIN', 0);
die 'Mismatched victory slots' unless @$ja == @$a && @$a == @$b;
my @victories;
my %victory_actions;
for my $i (0..$#$ja) {
    my $file = $i < 4543 ? 'MESJ_WIN.BIN' : 'MESE_WIN.BIN';
    my $r = $i < 4543 ? $a->[$i] : $b->[$i];
    my $s = $r->{text};
    my $action = $s =~ /[A-Za-z]/ ? 'TRADUCIR_DIALOGO' : 'CONSERVAR_SIMBOLOS';
    die 'Unexpected placeholder in selected bank' if $s =~ /^\s*X\s*$/;
    $victory_actions{$action}++;
    push @victories, [sprintf('WIN-%04d',$i+1), $file, sprintf('0x%X',$r->{offset}), $ja->[$i]{text}, $s, $action, protected_terms($s), '', 'Unidad: línea, no conversación. Hablante y contexto por mapear. Conservar nombres propios y técnicas citadas.'];
}
csv('analisis/dialogos-victoria.csv', [qw(id archivo offset japones ingles accion terminos_protegidos_detectados espanol observacion)], \@victories);

my $dm = message_strings('MESE_DM.BIN', 0);
my $dm_original = message_strings('MESE_DM.BIN', 1);
die 'Mismatched ending slots' unless @$dm == @$dm_original;
my @endings;
my %ending_actions;
for my $i (0..$#$dm) {
    my $s = $dm->[$i]{text};
    my $action = $s !~ /[A-Za-z]/ ? 'CONSERVAR_SIMBOLOS'
        : $s =~ /^THE (?:GREATEST WARRIOR|INCREDIBLE DUO|STRONGEST TRIO)/ ? 'CONSERVAR_TITULO'
        : 'TRADUCIR_NARRACION';
    $ending_actions{$action}++;
    push @endings, [sprintf('END-%03d',$i+1), 'MESE_DM.BIN', sprintf('0x%X',$dm->[$i]{offset}), $dm_original->[$i]{text}, $s, $action, '', 'Conservar símbolos, nombres y el título Millionaire Fighting Tournament cuando aparezca partido entre líneas.'];
}
csv('analisis/finales.csv', [qw(id archivo offset ingles_original ingles_parche accion espanol observacion)], \@endings);

sub entities {
    my ($s) = @_;
    $s =~ s/&#x([0-9a-f]+);/chr(hex($1))/egi;
    $s =~ s/&#(\d+);/chr($1)/eg;
    my %entities = (amp=>'&', lt=>'<', gt=>'>', quot=>'"', apos=>"'", nbsp=>' ', rsquo=>"'", lsquo=>"'", rdquo=>'"', ldquo=>'"', hellip=>'...', mdash=>'—', ndash=>'–');
    $s =~ s/&([A-Za-z]+);/exists $entities{$1} ? $entities{$1} : "&$1;"/eg;
    return $s;
}
my @bonus;
my %bonus_actions;
my %bonus_files;
for my $path (bsd_glob('analisis/ingles/DPWWW/*.HTML')) {
    my $html = decode('shiftjis', load($path), FB_CROAK);
    $html =~ s/<!--.*?-->//sg;
    $html =~ s/<head\b.*?<\/head>//sig;
    my ($file) = $path =~ m{([^/]+)$};
    my $seq = 0;
    my $context = '';
    while ($html =~ /(<[^>]+>)|([^<]+)/g) {
        if (defined $1) { $context = $1; next; }
        my $s = entities($2);
        $s =~ s/\s+/ /g;
        $s =~ s/^\s+|\s+$//g;
        next unless $s =~ /[A-Za-z0-9]/;
        $seq++;
        my $interview = $file =~ /^(?:ENDOU|FUNAMIZU|ISE|KAMINAGUCHI|KONDOU|NAGAYAMA|PLANNERS|SHINKIRO|YAMAZAKI)\.HTML$/;
        my $action = $s =~ /\?/ || length($s) > 110 ? 'TRADUCIR_PROSA'
            : $s =~ /[a-z]/ && $s =~ /\s/ && $s =~ /[.!]/ ? 'TRADUCIR_PROSA'
            : 'REVISAR_TITULO_NOMBRE_O_ETIQUETA';
        if ($file =~ /^MAIN/ && $s =~ /^(?:A save file|Watch the original|Interviews translated|Press )/) { $action = 'TRADUCIR_DESCRIPCION'; }
        $bonus_actions{$action}++;
        $bonus_files{$file}++;
        push @bonus, ["BONUS-$file-$seq", "DPWWW/$file", $seq, $context, $s, $action, protected_terms($s), '', $interview ? 'Entrevista: traducir preguntas y respuestas; conservar nombres, obras y técnicas. Segmentos HTML, no párrafos completos.' : 'Conservar títulos y enlaces técnicos. Los rótulos y créditos requieren revisión de alcance.'];
    }
}
csv('analisis/bonus-mode.csv', [qw(id archivo segmento etiqueta_previa ingles accion terminos_protegidos_detectados espanol observacion)], \@bonus);

# ASCII candidates are deliberately separate: graphics and custom encodings
# are not covered, and executable data can contain non-user-facing strings.
my @exe_candidates;
while ($exe =~ /([\x20-\x7E]{5,})\x00/g) {
    my $s = $1;
    my $offset = $-[1];
    next unless $s =~ /\b[A-Za-z]{3,}\b.*\s.*\b[A-Za-z]{2,}\b/;
    next if $s =~ m{[/\\]} || length($s) > 250;
    my $action = $s =~ /\b(?:please|press|select|save|load|memory|card|overwrite|deleted|format|data|controller)\b/i
        ? 'REVISAR_MENSAJE_O_INSTRUCCION' : 'REVISAR_TITULO_O_TEXTO_INTERNO';
    push @exe_candidates, [sprintf('0x%X',$offset),$s,$action,'','Extracción heurística; no confirma que aparezca en pantalla.'];
}
csv('analisis/ejecutable-candidatos.csv', [qw(offset ingles accion espanol observacion)], \@exe_candidates);

# A directly inspected group of menu descriptions. Unlike the broad executable
# scan above, retain short continuations such as "and special moves.".
my @descriptions;
my $description_block = substr($exe, 0x18937C, 0x1896F0 - 0x18937C);
while ($description_block =~ /([\x20-\x7E]{3,})\x00/g) {
    my $s = $1;
    my $offset = 0x18937C + $-[1];
    next unless $s =~ /[A-Za-z]/;
    push @descriptions, [sprintf('DESC-%02d', scalar(@descriptions)+1), '1ST_READ.BIN', sprintf('0x%X',$offset), $s, 'TRADUCIR_DESCRIPCION', protected_terms($s), '', 'Descripción de menú; varias entradas pueden formar una oración. Conservar nombres de modos y mecánicas.'];
}
csv('analisis/descripciones-juego.csv', [qw(id archivo offset ingles accion terminos_protegidos_detectados espanol observacion)], \@descriptions);

my %summary = (
    unit => 'Entradas físicas/líneas; no equivalen a conversaciones ni frases completas',
    victory => {slots=>scalar(@victories), actions=>\%victory_actions},
    endings => {slots=>scalar(@endings), actions=>\%ending_actions},
    bonus => {segments=>scalar(@bonus), files=>\%bonus_files, actions=>\%bonus_actions},
    executable_heuristic_candidates => scalar(@exe_candidates),
    inspected_menu_description_lines => scalar(@descriptions),
    move_list_preliminary_terms => scalar(@moves),
    scope => 'Diálogos y descripciones, incluido Bonus Mode. Conservar movimientos, comandos, títulos y nombres propios.',
    limitations => ['Clasificación preliminar; revisar nombres, títulos y técnicas dentro de cada frase.', 'Hablantes y referencias de conversaciones aún sin mapear.', 'Gráficos con texto y subtítulos incrustados en vídeo aún sin inventario visual.', 'La extracción no prueba compatibilidad de la fuente con español ni reinserción.'],
);
open my $json, '>:encoding(UTF-8)', 'analisis/resumen.json' or die $!;
print $json JSON::PP->new->canonical->pretty->encode(\%summary);
print JSON::PP->new->canonical->pretty->encode(\%summary);
