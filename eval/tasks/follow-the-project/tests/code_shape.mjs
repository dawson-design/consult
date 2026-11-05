// Static shape analysis of TypeScript and JavaScript source for the simplicity
// and house-default rule checks in code_shape.py, which runs this script and
// turns its facts into scores. Synced into each code task's tests/ by
// eval/scripts/sync_tests.py; do not edit the copy under tests/.
//
//   node code_shape.mjs <root> <relative file>...   prints one JSON object
//
// It reports facts, not verdicts: per-function size, nesting, decision points,
// unnamed compound conditions, and purity; classes; discriminated unions;
// throw sites; imports; environment reads; and declared names. The TypeScript
// compiler comes from CONSULT_ANALYZER_DIR (default /opt/eval/analyzer, which
// the shared Dockerfile installs at the version in eval/verifier/analyzer).
import { createRequire } from "node:module";
import path from "node:path";

const analyzerDir = process.env.CONSULT_ANALYZER_DIR ?? "/opt/eval/analyzer";
const ts = createRequire(path.join(analyzerDir, "package.json"))("typescript");
const K = ts.SyntaxKind;

const IO_MODULE_RE =
  /^(node:)?(fs|fs\/promises|http|https|http2|net|dgram|child_process|sqlite|readline|worker_threads|cluster|dns|tls)$|^(better-sqlite3|sqlite3|sqlite|pg|postgres|mysql2?|undici|axios|node-fetch|got|ky|express|fastify|koa|hono|@hono\/node-server)$/;
const RESULT_LIBRARY_RE = /^(neverthrow|ts-results(-es)?|true-myth|@badrap\/result|oxide\.ts|effect|fp-ts(\/.*)?|option-t)$/;
const IMPURE_GLOBAL_CALL_RE =
  /^(Date\.now|Math\.random|performance\.\w+|console\.\w+|process\.\w+|crypto\.(randomUUID|getRandomValues|randomBytes|randomInt)|fetch|setTimeout|setInterval|setImmediate|queueMicrotask|randomUUID|randomBytes|randomInt)$/;
const IO_METHOD_RE =
  /^(prepare|query|execute|listen|writeHead|setHeader|send|json|text|write|end|on|once|pipe|readFile\w*|writeFile\w*|appendFile\w*|mkdir\w*|readdir\w*|unlink\w*|rm\w*|stat\w*|existsSync)$/;
const DB_RECEIVER_RE = /(stmt|statement|db|database|sql|conn|connection|pool|client|tx)$/i;
const DB_METHOD_RE = /^(get|all|run|iterate|exec)$/;
const MUTATING_METHOD_RE = /^(push|pop|shift|unshift|splice|sort|reverse|set|delete|clear|add|fill|copyWithin)$/;
const RESULT_DISCRIMINANT_RE = /^(ok|success|isOk|isErr|isSuccess)$/;
const RESULT_TAG_RE = /^(ok|err|error|success|failure|fail)$/i;
const BUG_FUNCTION_RE = /assert|unreachable|never|invariant|exhaust/i;
// A plain built-in error marks a bug check (a broken invariant); a failure callers
// must handle has its own class, or is a Result, so only those count as expected.
const BUILT_IN_ERROR_RE = /^(new\s+)?(Error|TypeError|RangeError)\s*\(/;
const BUG_MESSAGE_RE = /unreachable|unexpected|invariant|impossible|exhaustive|\bbug\b|should not happen|never happen/i;

const CONTROL_KINDS = new Set([
  K.IfStatement, K.ForStatement, K.ForInStatement, K.ForOfStatement, K.WhileStatement,
  K.DoStatement, K.SwitchStatement, K.TryStatement,
]);
const FUNCTION_KINDS = new Set([
  K.FunctionDeclaration, K.MethodDeclaration, K.ArrowFunction, K.FunctionExpression,
  K.Constructor, K.GetAccessor, K.SetAccessor,
]);

/** Analyze files under root; returns the facts object printed as JSON. */
function analyze(root, relFiles) {
  const files = relFiles.map((rel) => path.resolve(root, rel));
  const program = ts.createProgram(files, {
    allowJs: true, checkJs: false, noEmit: true, strict: true, skipLibCheck: true, types: [],
    target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext,
    moduleResolution: ts.ModuleResolutionKind.Bundler, allowImportingTsExtensions: true,
  });
  const checker = program.getTypeChecker();
  const facts = { functions: [], classes: [], unions: [], throws: [], imports: {}, env: [], argv: false,
    names: [], interfaces: {}, abstractClasses: 0, resultLibrary: false, zodImported: false, zodParseCalls: 0,
    sharedMutable: [] };
  const recordsByNode = new Map();
  const classByNode = new Map();
  const edges = [];
  const relOf = (sf) => path.relative(root, sf.fileName).split(path.sep).join("/");
  const sources = files.map((f) => program.getSourceFile(f)).filter(Boolean);
  const analyzed = new Set(sources.map((sf) => sf.fileName));

  for (const sf of sources) {
    facts.imports[relOf(sf)] = [];
    const ctx = { checker, sf, rel: relOf(sf), facts, recordsByNode, classByNode, edges, analyzed, root };
    walk(sf, ctx, null, 0);
  }
  propagateImpurity(facts, recordsByNode, edges);
  facts.functions = facts.functions.map(({ node, calls, ...rest }) => rest);
  return facts;
}

function walk(node, ctx, fn, depth) {
  if (FUNCTION_KINDS.has(node.kind) && node.body) {
    const record = functionRecord(node, ctx);
    walk(node.body, ctx, record, 0);
    return;
  }
  noteNode(node, ctx, fn);
  if (fn && node.kind === K.IfStatement) {
    walkIf(node, ctx, fn, depth);
    return;
  }
  if (fn && CONTROL_KINDS.has(node.kind)) {
    fn.nesting = Math.max(fn.nesting, depth + 1);
    walkChildren(node, ctx, fn, depth + 1);
    return;
  }
  walkChildren(node, ctx, fn, depth);
}

function walkChildren(node, ctx, fn, depth) {
  ts.forEachChild(node, (child) => walk(child, ctx, fn, depth));
}

/** An else-if stays at its parent's depth, so a chain counts as one level. */
function walkIf(node, ctx, fn, depth) {
  fn.nesting = Math.max(fn.nesting, depth + 1);
  walk(node.expression, ctx, fn, depth + 1);
  walk(node.thenStatement, ctx, fn, depth + 1);
  if (!node.elseStatement) return;
  if (node.elseStatement.kind === K.IfStatement) {
    noteNode(node.elseStatement, ctx, fn);
    walkIf(node.elseStatement, ctx, fn, depth);
  } else {
    walk(node.elseStatement, ctx, fn, depth + 1);
  }
}

function functionRecord(node, ctx) {
  const { sf } = ctx;
  const record = {
    node, file: ctx.rel, name: functionName(node), line: sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1,
    lines: codeLines(node.getText(sf)), nesting: 0, decisions: 0, logic: 0, compound: 0,
    params: node.parameters.length, boolParams: node.parameters.filter(isBooleanParam).length,
    block: node.body.kind === K.Block, constructor: node.kind === K.Constructor, reasons: [], calls: [],
  };
  ctx.facts.functions.push(record);
  ctx.recordsByNode.set(node, record);
  if (node.name && ts.isIdentifier(node.name)) ctx.facts.names.push({ kind: "function", name: node.name.text });
  for (const param of node.parameters) noteName(param, ctx);
  noteReturnType(node, ctx);
  return record;
}

function functionName(node) {
  if (node.name && ts.isIdentifier(node.name)) return node.name.text;
  if (node.kind === K.Constructor) return "constructor";
  const parent = node.parent;
  if (parent && (ts.isVariableDeclaration(parent) || ts.isPropertyAssignment(parent) || ts.isPropertyDeclaration(parent))) {
    return ts.isIdentifier(parent.name) ? parent.name.text : "<anonymous>";
  }
  return "<callback>";
}

function codeLines(text) {
  return text.split("\n").filter((line) => {
    const t = line.trim();
    return t && !t.startsWith("//") && !t.startsWith("/*") && !t.startsWith("*");
  }).length;
}

function isBooleanParam(param) {
  return param.type?.kind === K.BooleanKeyword;
}

/** Facts one node contributes to its file and to the function that contains it. */
function noteNode(node, ctx, fn) {
  noteFileFacts(node, ctx, fn);
  if (!fn) return;
  noteDecision(node, fn);
  noteLogic(node, ctx, fn);
  noteCompound(node, ctx, fn);
  noteImpurity(node, ctx, fn);
}

/** Decisions that are business logic, not plumbing: a non-trivial condition, a loop, or a switch case. */
function noteLogic(node, ctx, fn) {
  const condition = ts.isIfStatement(node) || ts.isWhileStatement(node) || ts.isDoStatement(node)
    ? node.expression
    : ts.isConditionalExpression(node) ? node.condition : null;
  if (condition) fn.logic += logicalOperands(stripParens(condition)).filter((o) => !isTrivialCheck(o, ctx)).length ? 1 : 0;
  const loops = [K.ForStatement, K.ForInStatement, K.ForOfStatement, K.CaseClause];
  if (loops.includes(node.kind)) fn.logic += 1;
}

function noteDecision(node, fn) {
  const kinds = [K.IfStatement, K.ConditionalExpression, K.CaseClause, K.ForStatement, K.ForInStatement,
    K.ForOfStatement, K.WhileStatement, K.DoStatement, K.CatchClause];
  if (kinds.includes(node.kind)) fn.decisions += 1;
  if (ts.isBinaryExpression(node) && isLogical(node.operatorToken.kind)) fn.decisions += 1;
}

function isLogical(kind) {
  return kind === K.AmpersandAmpersandToken || kind === K.BarBarToken || kind === K.QuestionQuestionToken;
}

function noteCompound(node, ctx, fn) {
  const condition = ts.isIfStatement(node) || ts.isWhileStatement(node) || ts.isDoStatement(node)
    ? node.expression
    : ts.isConditionalExpression(node) ? node.condition : null;
  if (!condition) return;
  const operands = logicalOperands(stripParens(condition));
  if (operands.length >= 2 && operands.filter((o) => !isTrivialCheck(o, ctx)).length >= 2) fn.compound += 1;
}

function stripParens(node) {
  while (ts.isParenthesizedExpression(node)) node = node.expression;
  return node;
}

function logicalOperands(node) {
  node = stripParens(node);
  const joined = ts.isBinaryExpression(node)
    && (node.operatorToken.kind === K.AmpersandAmpersandToken || node.operatorToken.kind === K.BarBarToken);
  return joined ? [...logicalOperands(node.left), ...logicalOperands(node.right)] : [node];
}

/** Null and bounds checks need no name (core rule 4); a boolean flag's truthiness is a real check. */
function isTrivialCheck(node, ctx) {
  node = stripParens(node);
  if (ts.isPrefixUnaryExpression(node) && node.operator === K.ExclamationToken) return isTrivialCheck(node.operand, ctx);
  if (ts.isPropertyAccessExpression(node) && RESULT_DISCRIMINANT_RE.test(node.name.text)) return true;
  if (ts.isIdentifier(node) || ts.isPropertyAccessExpression(node)) return !isBooleanTyped(node, ctx);
  if (!ts.isBinaryExpression(node)) return false;
  const text = `${node.left.getText()} ${node.right.getText()}`;
  return /\b(null|undefined)\b|\.(length|size)\b|(^|\s)0$/.test(text);
}

function isBooleanTyped(node, ctx) {
  try {
    return Boolean(ctx.checker.getTypeAtLocation(node).flags & ts.TypeFlags.BooleanLike);
  } catch {
    return false;
  }
}

function noteImpurity(node, ctx, fn) {
  if (node.kind === K.AwaitExpression || node.kind === K.YieldExpression) fn.reasons.push("await");
  if (ts.isNewExpression(node) && node.expression.getText() === "Date" && !node.arguments?.length) {
    fn.reasons.push("clock");
  }
  if (ts.isPropertyAccessExpression(node) && node.expression.getText() === "process" && !isCallee(node)) {
    fn.reasons.push("process");
  }
  if (ts.isCallExpression(node)) noteCall(node, ctx, fn);
  if (isMutation(node)) noteMutation(mutationTarget(node), ctx, fn);
}

function isCallee(node) {
  return ts.isCallExpression(node.parent) && node.parent.expression === node;
}

function noteCall(call, ctx, fn) {
  const callee = stripParens(call.expression);
  const text = callee.getText();
  if (IMPURE_GLOBAL_CALL_RE.test(text) && !isLocallyDeclared(rootIdentifier(callee), ctx)) fn.reasons.push(`call:${text}`);
  if (ts.isPropertyAccessExpression(callee)) noteMethodCall(callee, ctx, fn);
  const root = rootIdentifier(callee);
  if (root && importedFrom(root, ctx, IO_MODULE_RE)) fn.reasons.push(`io:${text}`);
  if (returnsPromise(call, ctx)) fn.reasons.push("async-call");
  const target = resolveFunction(ts.isPropertyAccessExpression(callee) ? callee.name : callee, ctx);
  if (target) ctx.edges.push([fn, target]);
}

function noteMethodCall(callee, ctx, fn) {
  const method = callee.name.text;
  const receiver = stripParens(callee.expression);
  const receiverText = receiver.getText();
  if (receiverText === "Promise" || receiverText === "JSON" || receiverText === "Object") return;
  if (IO_METHOD_RE.test(method)) fn.reasons.push(`io-method:${method}`);
  if (DB_METHOD_RE.test(method) && DB_RECEIVER_RE.test(receiverText)) fn.reasons.push(`db:${method}`);
  if (MUTATING_METHOD_RE.test(method)) noteMutation(receiver, ctx, fn, true);
}

function isMutation(node) {
  if (ts.isBinaryExpression(node)) {
    const k = node.operatorToken.kind;
    return k >= K.FirstAssignment && k <= K.LastAssignment;
  }
  return (ts.isPrefixUnaryExpression(node) || ts.isPostfixUnaryExpression(node))
    && (node.operator === K.PlusPlusToken || node.operator === K.MinusMinusToken);
}

function mutationTarget(node) {
  return ts.isBinaryExpression(node) ? node.left : node.operand;
}

/** Writes through `this`, a parameter's members, or a binding declared outside the function. */
function noteMutation(target, ctx, fn, viaMethod = false) {
  target = stripParens(target);
  if (ts.isObjectLiteralExpression(target) || ts.isArrayLiteralExpression(target)) return;
  const root = rootIdentifier(target);
  if (!root) return;
  if (root.kind === K.ThisKeyword) {
    if (fn.constructor) return;
    fn.reasons.push("this-mutation");
    const owner = ctx.classByNode.get(enclosingClass(fn.node));
    if (owner) owner.thisMutation = true;
    return;
  }
  const decl = declarationOf(root, ctx);
  if (!decl) return;
  const fnNode = fn.node;
  const isMember = viaMethod || target !== root;
  if (ts.isParameter(decl) && decl.parent === fnNode) {
    if (isMember) fn.reasons.push("mutates-param");
    return;
  }
  if (isInside(decl, fnNode)) return;
  fn.reasons.push("mutates-outer");
  if (isModuleLevel(decl)) ctx.facts.sharedMutable.push({ file: relOfDecl(decl, ctx), name: root.getText() });
}

function enclosingClass(node) {
  let a = node.parent;
  while (a && !ts.isClassLike(a)) a = a.parent;
  return a;
}

function rootIdentifier(node) {
  node = stripParens(node);
  while (ts.isPropertyAccessExpression(node) || ts.isElementAccessExpression(node) || ts.isNonNullExpression(node)
    || ts.isParenthesizedExpression(node) || ts.isCallExpression(node)) {
    node = node.expression;
  }
  return ts.isIdentifier(node) || node.kind === K.ThisKeyword ? node : null;
}

function symbolOf(identifier, ctx) {
  const symbol = ctx.checker.getSymbolAtLocation(identifier);
  if (!symbol) return null;
  return symbol.flags & ts.SymbolFlags.Alias ? safeAliased(symbol, ctx) : symbol;
}

function safeAliased(symbol, ctx) {
  try {
    return ctx.checker.getAliasedSymbol(symbol);
  } catch {
    return symbol;
  }
}

function declarationOf(identifier, ctx) {
  const raw = ctx.checker.getSymbolAtLocation(identifier);
  if (!raw) return null;
  if (raw.flags & ts.SymbolFlags.Alias) return raw.declarations?.[0] ?? null;
  return raw.valueDeclaration ?? raw.declarations?.[0] ?? null;
}

function isLocallyDeclared(identifier, ctx) {
  if (!identifier || identifier.kind === K.ThisKeyword) return false;
  const decl = declarationOf(identifier, ctx);
  return Boolean(decl && ctx.analyzed.has(decl.getSourceFile().fileName));
}

function importedFrom(identifier, ctx, moduleRe) {
  if (identifier.kind === K.ThisKeyword) return false;
  const raw = ctx.checker.getSymbolAtLocation(identifier);
  const decl = raw?.declarations?.[0];
  if (!decl) return false;
  let node = decl;
  while (node && !ts.isImportDeclaration(node)) node = node.parent;
  return Boolean(node && moduleRe.test(node.moduleSpecifier.text));
}

function isInside(decl, fnNode) {
  return decl.getSourceFile() === fnNode.getSourceFile() && decl.pos >= fnNode.pos && decl.end <= fnNode.end;
}

function isModuleLevel(decl) {
  let node = decl.parent;
  while (node && !ts.isSourceFile(node)) {
    if (FUNCTION_KINDS.has(node.kind) || ts.isClassLike(node) || ts.isBlock(node)) return false;
    node = node.parent;
  }
  return Boolean(node) && ts.isVariableDeclaration(decl);
}

function relOfDecl(decl, ctx) {
  return path.relative(ctx.root, decl.getSourceFile().fileName).split(path.sep).join("/");
}

function returnsPromise(call, ctx) {
  try {
    const type = ctx.checker.getTypeAtLocation(call);
    return type?.symbol?.name === "Promise";
  } catch {
    return false;
  }
}

function resolveFunction(identifier, ctx) {
  if (!identifier || !ts.isIdentifier(identifier)) return null;
  const symbol = symbolOf(identifier, ctx);
  const decl = symbol?.valueDeclaration;
  if (!decl) return null;
  if (FUNCTION_KINDS.has(decl.kind)) return decl;
  if (ts.isVariableDeclaration(decl) && decl.initializer && FUNCTION_KINDS.has(stripParens(decl.initializer).kind)) {
    return stripParens(decl.initializer);
  }
  return null;
}

function propagateImpurity(facts, recordsByNode, edges) {
  const resolved = edges.map(([caller, target]) => [caller, recordsByNode.get(target)]).filter(([, t]) => t);
  let changed = true;
  while (changed) {
    changed = false;
    for (const [caller, callee] of resolved) {
      if (callee.reasons.length && !caller.reasons.some((r) => r.startsWith("calls:")) && callee !== caller) {
        caller.reasons.push(`calls:${callee.name}`);
        changed = true;
      }
    }
  }
  for (const record of facts.functions) record.pure = record.reasons.length === 0;
}

/** File-level facts: imports, classes, types, throws, env reads, and declared names. */
function noteFileFacts(node, ctx, fn) {
  if (ts.isImportDeclaration(node)) noteImport(node, ctx);
  if (ts.isClassLike(node)) noteClass(node, ctx);
  if (ts.isInterfaceDeclaration(node)) noteInterface(node, ctx);
  if (ts.isTypeAliasDeclaration(node)) noteTypeAlias(node, ctx);
  if (ts.isThrowStatement(node)) noteThrow(node, ctx, fn);
  noteEnv(node, ctx);
  noteName(node, ctx);
  if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)
    && /^(safe)?[pP]arse(Async)?$/.test(node.expression.name.text) && !/^JSON\b/.test(node.expression.getText())) {
    ctx.facts.zodParseCalls += 1;
  }
}

function noteImport(node, ctx) {
  const spec = node.moduleSpecifier.text;
  if (spec === "zod" || spec.startsWith("zod/")) ctx.facts.zodImported = true;
  if (RESULT_LIBRARY_RE.test(spec)) ctx.facts.resultLibrary = true;
  if (!spec.startsWith(".")) return;
  const resolved = path.resolve(path.dirname(ctx.sf.fileName), spec);
  const candidates = [resolved, ...[".ts", ".tsx", ".js", ".mjs", "/index.ts", "/index.js"].map((s) => resolved + s)];
  const target = candidates.find((c) => ctx.analyzed.has(c) || ctx.analyzed.has(c.replace(/\.js$/, ".ts")));
  if (target) {
    const file = ctx.analyzed.has(target) ? target : target.replace(/\.js$/, ".ts");
    ctx.facts.imports[ctx.rel].push(path.relative(ctx.root, file).split(path.sep).join("/"));
  }
}

function noteClass(node, ctx) {
  const heritage = (node.heritageClauses ?? []).find((h) => h.token === K.ExtendsKeyword);
  const extendsText = heritage ? heritage.types[0].expression.getText() : null;
  const members = node.members ?? [];
  const methods = members.filter((m) => ts.isMethodDeclaration(m) || ts.isGetAccessor(m) || ts.isSetAccessor(m)).length;
  const mutableFields = members.filter((m) => ts.isPropertyDeclaration(m) && !isReadonly(m) && !isStatic(m)).length;
  const isAbstract = (ts.getModifiers(node) ?? []).some((m) => m.kind === K.AbstractKeyword);
  if (isAbstract) ctx.facts.abstractClasses += 1;
  const implemented = (node.heritageClauses ?? []).filter((h) => h.token === K.ImplementsKeyword)
    .flatMap((h) => h.types.map((t) => t.expression.getText()));
  for (const name of implemented) ctx.facts.interfaces[name] = (ctx.facts.interfaces[name] ?? 0) + 1;
  const record = {
    file: ctx.rel, name: node.name?.text ?? "<anonymous>", extends: extendsText,
    isError: Boolean(extendsText && /Error$/.test(extendsText)), methods, mutableFields, thisMutation: false,
  };
  ctx.facts.classes.push(record);
  ctx.classByNode.set(node, record);
  if (node.name) ctx.facts.names.push({ kind: "class", name: node.name.text });
}

function isReadonly(member) {
  return (ts.getModifiers(member) ?? []).some((m) => m.kind === K.ReadonlyKeyword);
}

function isStatic(member) {
  return (ts.getModifiers(member) ?? []).some((m) => m.kind === K.StaticKeyword);
}

function noteInterface(node, ctx) {
  if (!(node.name.text in ctx.facts.interfaces)) ctx.facts.interfaces[node.name.text] ??= 0;
  ctx.facts.names.push({ kind: "type", name: node.name.text });
}

function noteTypeAlias(node, ctx) {
  ctx.facts.names.push({ kind: "type", name: node.name.text });
  const symbol = ctx.checker.getSymbolAtLocation(node.name);
  if (!symbol) return;
  const union = describeUnion(ctx.checker.getDeclaredTypeOfSymbol(symbol), ctx);
  if (union) ctx.facts.unions.push({ file: ctx.rel, name: node.name.text, ...union });
}

function noteReturnType(node, ctx) {
  try {
    const signature = ctx.checker.getSignatureFromDeclaration(node);
    if (!signature) return;
    let type = ctx.checker.getReturnTypeOfSignature(signature);
    if (type?.symbol?.name === "Promise") type = ctx.checker.getTypeArguments(type)?.[0] ?? type;
    const union = describeUnion(type, ctx);
    if (union?.result) ctx.facts.unions.push({ file: ctx.rel, name: `return:${functionName(node)}`, ...union });
  } catch {
    // A signature the checker cannot resolve says nothing about Result style.
  }
}

/** A union of object types with a literal discriminant: a Result type or a set of state variants. */
function describeUnion(type, ctx) {
  if (!type?.isUnion?.()) return null;
  const members = type.types.filter((t) => t.flags & (ts.TypeFlags.Object | ts.TypeFlags.Intersection));
  if (members.length < 2) return null;
  const propNames = members.map((m) => new Set(m.getProperties().map((p) => p.name)));
  const shared = [...propNames[0]].filter((name) => propNames.every((set) => set.has(name)));
  const discriminant = shared.find((name) => {
    const values = members.map((m) => literalValue(ctx.checker, m, name));
    return values.every((v) => v !== undefined) && new Set(values).size === values.length;
  });
  if (!discriminant) return null;
  const tags = members.map((m) => String(literalValue(ctx.checker, m, discriminant)));
  const result = RESULT_DISCRIMINANT_RE.test(discriminant) || tags.every((t) => RESULT_TAG_RE.test(t));
  const specific = propNames.filter((set) => [...set].some((name) => !shared.includes(name))).length;
  return { discriminant, tags, variants: members.length, specificVariants: specific, result };
}

function literalValue(checker, type, name) {
  const prop = type.getProperty(name);
  if (!prop) return undefined;
  const propType = checker.getTypeOfSymbol(prop);
  if (propType.isStringLiteral?.() || propType.isNumberLiteral?.()) return propType.value;
  if (propType.flags & ts.TypeFlags.BooleanLiteral) return checker.typeToString(propType);
  return undefined;
}

function noteThrow(node, ctx, fn) {
  const expression = node.expression?.getText() ?? "";
  const inDefault = hasAncestor(node, (a) => a.kind === K.DefaultClause);
  const rethrow = isRethrow(node);
  const bugFunction = Boolean(fn && BUG_FUNCTION_RE.test(fn.name));
  ctx.facts.throws.push({
    file: ctx.rel, line: ctx.sf.getLineAndCharacterOfPosition(node.getStart(ctx.sf)).line + 1,
    function: fn?.name ?? null,
    expected: Boolean(fn) && !inDefault && !bugFunction && !rethrow && !BUG_MESSAGE_RE.test(expression)
      && !BUILT_IN_ERROR_RE.test(expression),
    inCatch: hasAncestor(node, (a) => a.kind === K.CatchClause),
  });
}

/** `throw e` inside `catch (e)`: passing on an error this code did not expect. */
function isRethrow(node) {
  let a = node.parent;
  while (a && !FUNCTION_KINDS.has(a.kind) && a.kind !== K.CatchClause) a = a.parent;
  const name = a?.kind === K.CatchClause ? a.variableDeclaration?.name.getText() : undefined;
  return Boolean(name) && node.expression?.getText() === name;
}

function hasAncestor(node, predicate) {
  for (let a = node.parent; a && !FUNCTION_KINDS.has(a.kind); a = a.parent) if (predicate(a)) return true;
  return false;
}

function noteEnv(node, ctx) {
  const isEnv = (n) => n && n.getText() === "process.env";
  if (ts.isPropertyAccessExpression(node) && isEnv(node.expression)) ctx.facts.env.push(node.name.text);
  if (ts.isElementAccessExpression(node) && isEnv(node.expression) && ts.isStringLiteral(node.argumentExpression)) {
    ctx.facts.env.push(node.argumentExpression.text);
  }
  if (ts.isVariableDeclaration(node) && isEnv(node.initializer) && ts.isObjectBindingPattern(node.name)) {
    for (const el of node.name.elements) ctx.facts.env.push((el.propertyName ?? el.name).getText());
  }
  if (ts.isPropertyAccessExpression(node) && node.getText() === "process.argv") ctx.facts.argv = true;
}

function noteName(node, ctx) {
  const named = ts.isVariableDeclaration(node) || ts.isParameter(node) || ts.isPropertySignature(node)
    || ts.isPropertyDeclaration(node) || ts.isMethodDeclaration(node) || ts.isEnumDeclaration(node);
  if (named && node.name && ts.isIdentifier(node.name)) ctx.facts.names.push({ kind: "value", name: node.name.text });
}

const [root, ...relFiles] = process.argv.slice(2);
process.stdout.write(JSON.stringify(analyze(root, relFiles)));
