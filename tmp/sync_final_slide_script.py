from pathlib import Path
import json
root=Path.cwd();out=root/'results/presentations/2026-09-17_sensibilidad'
slides=json.loads((out/'verification.json').read_text())
figures={4:'ba_adiciones.png',5:'respuesta_temprana.png',7:'ancho_de_banda.png',10:'control_triangulos_sbm.png',13:'control_del_kernel.png',14:'comunidades_er.png'}
deck='https://docs.google.com/presentation/d/1ZE-LmtIFOjXrr09gFOXzKS_KyRU5YGX1mrZFI4sAn7w/edit'
lines=['# Sensibilidad a perturbaciones estructurales','',f'[Presentación editada en Google Slides]({deck})','',
       'Guion de la versión final: 14 diapositivas, centradas en BA, ER y SBM. Las notas incluyen las condiciones experimentales y las fuentes.','']
for s in slides:
 texts=[x for x in s['text'] if x.strip()]
 title='Sensibilidad a perturbaciones estructurales' if s['slide']==1 else texts[0]
 lines.extend([f'## {s["slide"]}. {title}',''])
 body=texts[2:] if s['slide']==1 else texts[1:]
 for line in body:lines.extend([line,''])
 if s['slide'] in figures:
  name=figures[s['slide']]
  lines.extend([f'![{title}](//wsl.localhost/Ubuntu/home/artrivas/Thesis/results/presentations/2026-09-17_sensibilidad/{name})',''])
 lines.extend(['**Notas del orador**','',s['notes'],''])
(out/'guion_es.md').write_text('\n'.join(lines),encoding='utf-8')
print('Synchronized final Spanish script and six figure embeds with the verified Google Slides version.')
