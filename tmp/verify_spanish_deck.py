from pathlib import Path
import zipfile,xml.etree.ElementTree as ET,json,re
root=Path.cwd();out=root/'results/presentations/2026-09-17_sensibilidad'
ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
with zipfile.ZipFile(out/'avance6_revision.pptx') as z:
 slides=sorted([n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)],key=lambda n:int(re.search(r'(\d+)\.xml',n).group(1)))
 report=[]
 for i,n in enumerate(slides,1):
  tree=ET.fromstring(z.read(n));texts=[' '.join(x.itertext()) for x in tree.findall('.//a:t',ns)]
  notespath=f'ppt/notesSlides/notesSlide{i}.xml'
  notes=' '.join(t.text or '' for t in ET.fromstring(z.read(notespath)).findall('.//a:t',ns)) if notespath in z.namelist() else ''
  item={'slide':i,'text':texts,'images':len(tree.findall('.//p:pic',ns)), 'shapes':len(tree.findall('.//p:sp',ns)),
        'font_sizes':sorted(set(int(e.attrib['sz'])/100 for e in tree.iter() if 'sz' in e.attrib)),
        'autofit':[e.attrib for e in tree.findall('.//a:normAutofit',ns)],'notes':notes}
  report.append(item)
  print(i,'images',item['images'],'shapes',item['shapes'],'fonts',item['font_sizes'],'autofit',item['autofit'],'TEXT',texts)
 assert len(slides)==14,len(slides)
 assert sum(r['images'] for r in report)==6
 assert all(len(r['notes'])>100 for r in report)
 assert not any('Haz clic' in ' '.join(r['text']) or 'last week' in ' '.join(r['text']) for r in report)
 assert not any(re.search(r'z[yi]nc', ' '.join(r['text'])+' '+r['notes'], re.I) for r in report), 'Unexpected excluded dataset reference'
 (out/'verification.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
 print('Verified 14 slides, 6 embedded scientific figures, Spanish content, notes on every slide, and no ZINC/ZYNC references.')
