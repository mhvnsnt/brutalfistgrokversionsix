#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const root=path.resolve(process.env.BANNON_SOURCE ?? 'BannonSource');
const index=path.join(root,'assets/moves/clips/index.json');
const map=path.join(root,'assets/moves/fbx_move_map.json');
const out=path.resolve('native/media/characters/_bannon_animation_bridge');

if(!fs.existsSync(index)) throw new Error('Bannon clips index missing');
const clips=JSON.parse(fs.readFileSync(index,'utf8'));
const moveMap=fs.existsSync(map)?JSON.parse(fs.readFileSync(map,'utf8')):null;

const rows=(Array.isArray(clips)?clips:Object.values(clips)).map(x=>({
  id:x.id ?? x.key ?? x.name ?? x.file,
  file:x.file ?? x.src ?? x.source,
  duration:x.dur ?? x.duration ?? null,
  bones:x.bones ?? null
})).filter(x=>x.id && x.file);

fs.mkdirSync(out,{recursive:true});
fs.writeFileSync(path.join(out,'clips.json'),JSON.stringify({
  schema:1,
  source:'BannonSource/assets/moves/clips/index.json',
  count:rows.length,
  clips:rows
},null,2)+'\n');

fs.writeFileSync(path.join(out,'move-map.json'),JSON.stringify({
  schema:1,
  source:'BannonSource/assets/moves/fbx_move_map.json',
  note:'Use this map to produce Schwarzerblitz animation resources. Do not silently substitute procedural clips.',
  map:moveMap ?? {}
},null,2)+'\n');

console.log(`Indexed ${rows.length} real Bannon clips for native conversion.`);
