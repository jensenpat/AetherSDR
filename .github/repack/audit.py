import struct, pathlib, json, hashlib, sys, zipfile
old,new,symbols=map(pathlib.Path,sys.argv[1:4])
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def files(root):return {p.relative_to(root).as_posix():p for p in root.rglob('*') if p.is_file()}
a,b=files(old),files(new)
# These SDK-generated package footprints are rebuilt when the manifest changes.
footprints={'AppxManifest.xml','AppxBlockMap.xml','[Content_Types].xml','AppxSignature.p7x','AppxMetadata/CodeIntegrity.cat'}
pa={k:v for k,v in a.items() if k not in footprints};pb={k:v for k,v in b.items() if k not in footprints}
assert pa.keys()==pb.keys(), 'Payload file inventory changed'
assert all(digest(v)==digest(pb[k]) for k,v in pa.items()), 'Payload bytes changed'
def pdb_identity(p):
 d=p.read_bytes();assert d[:24]==b'Microsoft C/C++ MSF 7.00\r\n',p
 block,_,_,size,_,mapblock=struct.unpack_from('<6I',d,32)
 count=(size+block-1)//block
 ids=struct.unpack_from('<'+'I'*count,d,mapblock*block)
 directory=b''.join(d[i*block:(i+1)*block] for i in ids)[:size]
 n=struct.unpack_from('<I',directory)[0];sizes=struct.unpack_from('<'+'I'*n,directory,4);pos=4+4*n
 streams=[]
 for s in sizes:
  count=0 if s==0xffffffff else (s+block-1)//block
  ids=struct.unpack_from('<'+'I'*count,directory,pos);pos+=count*4
  streams.append(ids)
 info=b''.join(d[i*block:(i+1)*block] for i in streams[1])[:sizes[1]]
 return info[12:28].hex(),struct.unpack_from('<I',info,8)[0]
def pe_identity(p):
 d=p.read_bytes()
 if d[:2]!=b'MZ':return None
 pe=struct.unpack_from('<I',d,60)[0];assert d[pe:pe+4]==b'PE\0\0'
 n=struct.unpack_from('<H',d,pe+6)[0];optsize=struct.unpack_from('<H',d,pe+20)[0];opt=pe+24
 magic=struct.unpack_from('<H',d,opt)[0];datadir=opt+(112 if magic==0x20b else 96)
 rva,size=struct.unpack_from('<II',d,datadir+6*8)
 sections=[]
 for i in range(n):
  vsize,va,rawsize,raw=struct.unpack_from('<4I',d,opt+optsize+40*i+8);sections.append((va,max(vsize,rawsize),raw))
 def offset(r):
  for va,size,raw in sections:
   if va<=r<va+size:return raw+r-va
  raise ValueError('Unmapped RVA')
 if not rva:return None
 off=offset(rva)
 for i in range(size//28):
  kind,sz,_,ptr=struct.unpack_from('<4I',d,off+i*28+12)
  if kind==2 and d[ptr:ptr+4]==b'RSDS':
   name=d[ptr+24:ptr+sz].split(b'\0')[0].decode('utf-8',errors='replace').replace('\\','/').split('/')[-1]
   return name.lower(),d[ptr+4:ptr+20].hex(),struct.unpack_from('<I',d,ptr+20)[0]
 return None
binary_ids={}
for name,p in pb.items():
 if p.suffix.lower() in ('.exe','.dll'):
  ident=pe_identity(p)
  if ident:binary_ids.setdefault(ident[0],[]).append((name,ident[1:]))
matched=[]
for p in symbols.glob('*.pdb'):
 identity=pdb_identity(p);matches=[name for name,ident in binary_ids.get(p.name.lower(),[]) if ident==identity]
 assert matches, f'No matching binary GUID/age for {p.name}'
 matched.append({'pdb':p.name,'guid':identity[0],'age':identity[1],'binaries':matches})
required=['AetherSDR.pdb','Qt6Core.pdb','Qt6Gui.pdb','Qt6Widgets.pdb']
assert all(x.lower() in [m['pdb'].lower() for m in matched] for x in required)
report={'payloadFilesUnchanged':len(pa),'matchedSymbols':matched,'symbolCount':len(matched)}
pathlib.Path('out/symbol-audit.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
