import csv, struct, json, collections, hashlib
from pathlib import Path
root=Path(__file__).resolve().parent.parent
b=(root/'analisis/original/MESJ_WIN.BIN').read_bytes(); u=lambda p:struct.unpack_from('<I',b,p)[0]
p=5108; offsets=[]
while p<298720:
 while p<298720 and b[p]==0:p+=1
 if p>=298720:break
 offsets.append(p);p=b.index(b'\0',p)+1
assert len(offsets)==8496
ids={o:f'WIN-{i:04d}' for i,o in enumerate(offsets,1)}
headers=[u(357504+4*i) for i in range(48)]
assert len(set(headers))==48
bounds=sorted(headers); blocks=[]; instances=[]
for order,h in enumerate(bounds):
 prev=298720 if order==0 else bounds[order-1]+416
 assert (h-prev)%4==0
 starts=[u(h+4*i) for i in range(104)]
 assert starts[0]==prev and all(prev<=v<h and v%4==0 for v in starts)
 assert all(a<b for a,b in zip(starts,starts[1:]))
 groups=[]
 for j,start in enumerate(starts):
  end=starts[j+1] if j<103 else h
  assert (end-start) in (4,8), (hex(h),j,hex(start),hex(end))
  members=[ids[u(k)] for k in range(start,end,4)]
  row={'indice_bloque_fisico':order,'indice_bloque_cabecera':headers.index(h),'indice_intervencion':j,'puntero_inicio':f'0x{h+4*j:X}','tabla_lineas_inicio':f'0x{start:X}','ids':members}
  groups.append(row);instances.append(row)
 blocks.append({'indice_fisico':order,'indice_cabecera':headers.index(h),'tabla_lineas':f'0x{prev:X}','indice_intervenciones':f'0x{h:X}','intervenciones':groups})
refs=collections.Counter(i for r in instances for i in r['ids']); dist=collections.Counter(len(x['ids']) for x in instances)
print('blocks',len(blocks),'instances',len(instances),'dist',dist,'distinct',len(refs),'missing',8496-len(refs),'duplicates',[(k,v) for k,v in refs.items() if v>1][:20]); print('last',blocks[-1]['intervenciones'][-3:]);print('header order',[x['indice_cabecera'] for x in blocks])
out={'fuente':'analisis/original/MESJ_WIN.BIN','sha256':hashlib.sha256(b).hexdigest(),'metodo':'Punteros de comienzo de intervención; el siguiente comienzo o el inicio de la tabla de índices marca el fin. Los IDs apuntan a cadenas físicas y pueden repetirse.','limites':'Una intervención visual de dos líneas no garantiza que ambas correspondan al mismo hablante, especialmente diálogos entre personajes.','bloques':blocks}
(root/'analisis/agrupacion-dialogos.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
missing=[f'WIN-{i:04d}' for i in range(1,8497) if f'WIN-{i:04d}' not in refs]
txt=f'''Análisis estructural de MESJ_WIN.BIN\nSHA-256: {hashlib.sha256(b).hexdigest()}\nCadenas físicas: {len(offsets)}. Cada cadena original se recupera desde 0x13F4 hasta 0x48EE0; CSV usa los mismos números físicos, aunque los offsets del CSV proceden de archivos reconstruidos.\nCabecera: dos punteros little-endian en 0 y 4: 0x57480 y 0x57540. La primera tabla contiene 48 punteros a índices de bloque. Su orden no coincide siempre con el orden físico. La segunda tabla contiene 48 punteros a estructuras anteriores al texto; su significado preciso no queda demostrado.\nCada bloque físico tiene una tabla de punteros de cadenas y, a continuación, 104 punteros little-endian a comienzos en esa tabla. El inicio siguiente marca el fin de cada intervención; la última termina donde empieza la tabla de 104 punteros. Son {len(instances)} intervenciones referenciadas: {dist[1]} de una línea y {dist[2]} de dos.\nPrimeros casos: WIN-0001+WIN-0002; WIN-0003 sola; WIN-0004+WIN-0005; WIN-0006 sola; WIN-0007+WIN-0008. Una pareja es una unidad visual, no necesariamente una única frase o hablante: WIN-0108 y WIN-0109 son dos voces distintas dentro del mismo cuadro. No redistribuir texto entre hablantes sin revisión semántica.\nIDs físicos distintos referenciados: {len(refs)}; sin referencia en estas tablas: {len(missing)}. Referencias repetidas: {[(k,v) for k,v in refs.items() if v>1]}. Los huecos o referencias repetidas deben examinarse antes de modificar datos compartidos.\nEl JSON conserva cada instancia, posición del puntero, índice físico y de cabecera, y los IDs en orden; no asigna nombres de personajes ni oponentes porque no se ha demostrado el mapeo. No identifica de forma fiable los cambios de hablante dentro de cada pareja. Se ha validado que cada inicio apunta a la tabla de líneas de su bloque, que son estrictamente crecientes y que todos los grupos tienen una o dos entradas.\nIDs sin referencia: {', '.join(missing)}\n'''
(root/'analisis/agrupacion-dialogos.txt').write_text(txt,encoding='utf-8')
