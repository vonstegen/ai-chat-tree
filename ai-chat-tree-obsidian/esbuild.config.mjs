import { build } from 'esbuild';

const production = process.argv.includes('--production');
const sourcemap = process.argv.includes('--sourcemap');
const watch = process.argv.includes('--watch');

build({
    bundle: true,
    format: 'cjs',
    entryPoints: ['main.ts'],
    external: ['obsidian'],
    jsx: 'transform',
    jsxFactory: 'h',
    jsxFragment: 'Fragment',
    minify: production,
    sourcemap,
    target: 'es2017',
    outfile: 'main.js',
    logLevel: 'silent',
}).then((ctx) => {
    if (watch) {
        process.on('SIGINT', () => process.exit(0));
    }
});
