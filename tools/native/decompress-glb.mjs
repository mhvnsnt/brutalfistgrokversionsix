#!/usr/bin/env node
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { MeshoptDecoder } from 'meshoptimizer';
import path from 'node:path';

const src = path.resolve(process.argv[2] ?? 'native/source/BANNON_rigged.glb');
const dst = path.resolve(process.argv[3] ?? 'native/source/BANNON_rigged.uncompressed.glb');

await MeshoptDecoder.ready;
const io = new NodeIO()
  .registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({ 'meshopt.decoder': MeshoptDecoder });
const doc = await io.read(src);
for (const ext of doc.getRoot().listExtensionsUsed()) {
  if (ext.extensionName === 'EXT_meshopt_compression') ext.dispose();
}
await io.write(dst, doc);
console.log(`decompressed ${src} -> ${dst}`);
