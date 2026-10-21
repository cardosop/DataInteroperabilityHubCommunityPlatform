#!/usr/bin/env node
// Helper invoked by scripts/e2e_metrics.py. Parses TypeScript/TSX via
// @typescript-eslint/parser and emits per-file metric counts as JSON on stdout.
//
// Usage:
//   node scripts/e2e_metrics_typescript.cjs <file1> <file2> ...
//
// The parser module lives in frontend/node_modules, so this script resolves
// that path explicitly rather than requiring the caller to cd into frontend/.

'use strict';

const fs = require('fs');
const path = require('path');
const { createRequire } = require('node:module');

const REPO_ROOT = path.resolve(__dirname, '..');
const FRONTEND_PKG = path.join(REPO_ROOT, 'frontend', 'package.json');

// Resolve as if requiring from frontend/package.json so the parser finds its
// own transitive deps via frontend/node_modules. Absolute-path require() does
// not honour modern `exports` maps, which is why a direct require fails.
let parser;
try {
  const frontendRequire = createRequire(FRONTEND_PKG);
  parser = frontendRequire('@typescript-eslint/parser');
} catch (err) {
  process.stderr.write(
    `e2e_metrics_typescript.cjs: cannot load @typescript-eslint/parser ` +
    `from ${FRONTEND_PKG}: ${err.message}\n`
  );
  process.exit(2);
}

const HTTP_METHODS = new Set(['get', 'post', 'put', 'patch', 'delete', 'head']);

/**
 * Return true when `node` is an ESTree AST node for an Identifier with `name`.
 */
function isIdent(node, name) {
  return node && node.type === 'Identifier' && node.name === name;
}

/**
 * Return true when `node` is the MemberExpression `<objectName>.<propertyName>`.
 * Works only for non-computed member access with Identifier object and property.
 */
function isMember(node, objectName, propertyName) {
  return (
    node &&
    node.type === 'MemberExpression' &&
    !node.computed &&
    isIdent(node.object, objectName) &&
    isIdent(node.property, propertyName)
  );
}

/**
 * Walk the AST calling `visit` on every node.
 * Iterative to avoid stack overflow on large files.
 */
function walk(root, visit) {
  const stack = [root];
  while (stack.length) {
    const node = stack.pop();
    if (!node || typeof node !== 'object') continue;
    if (Array.isArray(node)) {
      for (const child of node) stack.push(child);
      continue;
    }
    if (typeof node.type === 'string') visit(node);
    for (const key of Object.keys(node)) {
      // Skip parent back-refs and position metadata
      if (key === 'parent' || key === 'loc' || key === 'range') continue;
      const value = node[key];
      if (value && typeof value === 'object') stack.push(value);
    }
  }
}

/**
 * Count metric patterns in the AST. Returns an object with integer counts.
 */
function countForAst(ast) {
  const counts = {
    test_skip_true: 0,
    page_on_pageerror: 0,
    page_request_call: 0,
    verify_via_api_call: 0,
  };

  walk(ast, (node) => {
    if (node.type !== 'CallExpression') return;
    const callee = node.callee;

    // test.skip(true, ...) — first arg is the boolean literal true
    if (isMember(callee, 'test', 'skip')) {
      const firstArg = node.arguments && node.arguments[0];
      if (firstArg && firstArg.type === 'Literal' && firstArg.value === true) {
        counts.test_skip_true += 1;
      }
      return;
    }

    // page.on('pageerror', ...)
    if (isMember(callee, 'page', 'on')) {
      const firstArg = node.arguments && node.arguments[0];
      if (firstArg && firstArg.type === 'Literal' && firstArg.value === 'pageerror') {
        counts.page_on_pageerror += 1;
      }
      return;
    }

    // page.request.<METHOD>(...)  — callee is MemberExpression (page.request).METHOD
    if (
      callee &&
      callee.type === 'MemberExpression' &&
      !callee.computed &&
      callee.property &&
      callee.property.type === 'Identifier' &&
      HTTP_METHODS.has(callee.property.name) &&
      callee.object &&
      isMember(callee.object, 'page', 'request')
    ) {
      counts.page_request_call += 1;
      return;
    }

    // verifyViaApi(...) — bare identifier call
    if (isIdent(callee, 'verifyViaApi')) {
      counts.verify_via_api_call += 1;
      return;
    }
  });

  return counts;
}

function parseFile(filePath) {
  const src = fs.readFileSync(filePath, 'utf8');
  return parser.parse(src, {
    loc: false,
    range: false,
    tokens: false,
    comment: false,
    errorOnUnknownASTType: false,
    jsx: filePath.endsWith('.tsx') || filePath.endsWith('.jsx'),
    ecmaVersion: 'latest',
    sourceType: 'module',
  });
}

function main() {
  const files = process.argv.slice(2);
  const out = {};
  for (const f of files) {
    try {
      const ast = parseFile(f);
      out[f] = countForAst(ast);
    } catch (err) {
      process.stderr.write(`parse error in ${f}: ${err.message}\n`);
      process.exit(3);
    }
  }
  process.stdout.write(JSON.stringify(out));
}

main();
