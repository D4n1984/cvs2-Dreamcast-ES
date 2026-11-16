use strict; use warnings; use File::Path qw(make_path);
my ($track)=glob('roms/original/*Track 3*.bin');
# glob splits paths with spaces, so enumerate explicitly.
opendir(my $dh,'roms/original') or die $!; ($track)=map { 'roms/original/'.$_ } grep {/Track 3.*\.bin$/} readdir($dh); closedir $dh;
open(my $disc,'<:raw',$track) or die $!;
sub sectors { my($lba,$size)=@_; my $out=''; while($size>0){seek($disc,($lba-45000)*2352+16,0) or die $!; my $n=$size>2048?2048:$size; read($disc,my $buf,$n)==$n or die 'Short sector'; $out.=$buf;$size-=$n;$lba++}return $out; }
my $pvd=sectors(45016,2048); die 'Not ISO9660' unless substr($pvd,1,5) eq 'CD001';
make_path('analisis/original','analisis/ingles');
my @files;
sub directory { my($lba,$size,$prefix)=@_;my $data=sectors($lba,$size); my $pos=0; while($pos<length($data)){my $len=ord(substr($data,$pos,1));if(!$len){$pos=(int($pos/2048)+1)*2048;next}my $r=substr($data,$pos,$len);$pos+=$len;my($extent,$bytes)=unpack('Vx4V',substr($r,2,12));my $name=substr($r,33,ord(substr($r,32,1)));next if $name eq "\0"||$name eq "\1"; $name=~s/;\d+$//;my $path=$prefix.$name;if(ord(substr($r,25,1))&2){directory($extent,$bytes,$path.'/')}else{push @files,[$path,$extent,$bytes];if($path=~/^(?:MES[^\/]*\.BIN|FONT(?:_E)?\.BIN|S20RM04\.BIN|1ST_READ\.BIN|DC\d+E?TEX\.BIN|DM\d+E?TEX\.BIN|DPFONT\/[^\/]+\.DAT|DPWWW\/[^\/]+\.HTML)$/){my $out='analisis/original/'.$path;$out=~m{^(.*)/};make_path($1);open(my $f,'>:raw',$out)or die $!;print $f sectors($extent,$bytes);close $f;print "$path $bytes\n"}}}}
my($root,$root_size)=unpack('Vx4V',substr($pvd,158,12));directory($root,$root_size,'');
open(my $list,'>:encoding(UTF-8)','analisis/archivos-disco.csv')or die $!;print $list "archivo,lba,bytes\n";for(@files){print $list join(',',@$_)."\n"}close $list;
