#!/usr/bin/env node
import { execFileSync, spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SCAFFOLD_ROOT = dirname(fileURLToPath(import.meta.url));
const TEMPLATE_ROOT = join(SCAFFOLD_ROOT, "templates", "frontend");
const VALIDATOR = join(SCAFFOLD_ROOT, "validate_scaffold.py");

const FIELD_TYPES = new Set(["string", "number", "boolean"]);

const USAGE = [
  "usage: node .agents/scaffold/frontend_feature.mjs <feature> --entity <Entity>",
  "         --field name:string --field quantity:number [--nullable <name>]",
  "         (--plan | --apply --approved <path-list-file>)",
  "",
  "<feature> is the kebab-case plural used for the directory, the route segment",
  "and the OpenAPI tag. The generated api/ and server/ modules reference the orval",
  "client by that tag, so `npm run generate:api` must run after the backend slice",
  "exists; `npm run typecheck` is what proves the generated names line up.",
].join("\n");

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exit(2);
}

function parseArgs(argv) {
  const options = { fields: [], nullable: [], plan: false, apply: false };
  const positional = [];
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--plan") options.plan = true;
    else if (token === "--apply") options.apply = true;
    else if (token === "--entity") options.entity = argv[++index];
    else if (token === "--field") options.fields.push(argv[++index]);
    else if (token === "--nullable") options.nullable.push(argv[++index]);
    else if (token === "--approved") options.approved = argv[++index];
    else if (token.startsWith("-")) fail(`unknown option ${token}\n\n${USAGE}`);
    else positional.push(token);
  }
  options.feature = positional[0];
  return options;
}

function repoRoot() {
  try {
    return execFileSync("git", ["rev-parse", "--show-toplevel"], {
      encoding: "utf8",
    }).trim();
  } catch {
    return resolve(SCAFFOLD_ROOT, "..", "..");
  }
}

function camel(value) {
  return value.replace(/-([a-z0-9])/g, (_match, letter) => letter.toUpperCase());
}

function pascal(value) {
  const head = camel(value);
  return head.charAt(0).toUpperCase() + head.slice(1);
}

function kebab(value) {
  return value
    .replace(/([a-z0-9])([A-Z])/g, "$1-$2")
    .replace(/_/g, "-")
    .toLowerCase();
}

function snake(value) {
  return kebab(value).replace(/-/g, "_");
}

function words(value) {
  return kebab(value).replace(/-/g, " ");
}

function titleCase(value) {
  return words(value)
    .split(" ")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function parseField(raw, nullable) {
  const [name, kind] = raw.split(":").map((part) => (part ?? "").trim());
  if (!name || !kind) fail(`--field ${raw} must be written as name:type`);
  if (!FIELD_TYPES.has(kind)) {
    fail(`field type ${kind} is not supported; use string, number or boolean`);
  }
  if (["id", "createdAt", "updatedAt", "created_at", "updated_at"].includes(name)) {
    fail(`field ${name} is provided by the template already`);
  }
  return {
    camel: camel(kebab(name)),
    snake: snake(name),
    label: titleCase(name),
    kind,
    nullable: nullable.includes(name),
  };
}

function sample(field, variant) {
  if (field.kind === "string") {
    return variant === 0 ? `"Sample ${field.label}"` : `"Updated ${field.label}"`;
  }
  if (field.kind === "number") return variant === 0 ? "1" : "2";
  return variant === 0 ? "true" : "false";
}

function zodExpression(field) {
  if (field.kind === "string") {
    return `z.string().min(1, "${field.label} is required")`;
  }
  if (field.kind === "number") return "z.coerce.number()";
  return "z.boolean()";
}

function operationName(handler, path, method) {
  const identifier = `${handler}${path}`.replace(/\W/g, "_") + `_${method}`;
  return identifier
    .split("_")
    .filter(Boolean)
    .map((part, index) =>
      index === 0 ? part : part.charAt(0).toUpperCase() + part.slice(1),
    )
    .join("");
}

function cellExpression(field) {
  const access = `item.${field.camel}`;
  if (field.kind === "boolean") {
    return field.nullable
      ? `${access} === null ? "—" : ${access} ? "Yes" : "No"`
      : `${access} ? "Yes" : "No"`;
  }
  return field.nullable ? `${access} ?? "—"` : access;
}

function indent(lines, spaces) {
  const pad = " ".repeat(spaces);
  return lines.map((line) => pad + line).join("\n");
}

function substitutions(feature, entity, fields) {
  const entityFile = kebab(entity);
  const entitySnake = snake(entity);
  const featureSnake = snake(feature);
  const invalidField =
    fields.find((field) => field.kind === "string") ??
    fields.find((field) => field.kind === "number");
  const validLiteral =
    "{ " + fields.map((f) => `${f.camel}: ${sample(f, 0)}`).join(", ") + " }";
  const invalidLiteral = invalidField
    ? "{ " +
      fields
        .map((f) =>
          f === invalidField
            ? `${f.camel}: ${f.kind === "string" ? '""' : '"not-a-number"'}`
            : `${f.camel}: ${sample(f, 0)}`,
        )
        .join(", ") +
      " }"
    : "{}";
  const invalidTest = invalidField
    ? [
        "",
        `  it("rejects an invalid ${words(invalidField.camel)}", () => {`,
        `    const result = create${pascal(entity)}Schema.safeParse(${invalidLiteral});`,
        "",
        "    expect(result.success).toBe(false);",
        "  });",
        "",
      ].join("\n")
    : "";

  return {
    "{{Entities}}": pascal(feature),
    "{{Entity}}": pascal(entity),
    "{{ENTITY}}": snake(entity).toUpperCase(),
    "{{entity-file}}": entityFile,
    "{{entity-words}}": words(entity),
    "{{entity}}": camel(entityFile),
    "{{feature-camel}}": camel(feature),
    "{{feature-words}}": words(feature),
    "{{feature}}": feature,
    "{{Title}}": titleCase(feature),
    "{{ReadDto}}": `${pascal(entity)}Read`,
    "{{CreateDto}}": `${pascal(entity)}Create`,
    "{{UpdateDto}}": `${pascal(entity)}Update`,
    "{{PageDto}}": `PaginatedResponse${pascal(entity)}Read`,
    "{{generated_module}}": `@/lib/api/generated/endpoints/${feature}/${feature}`,
    "{{opList}}": operationName(`list_${featureSnake}`, `/${feature}`, "get"),
    "{{opGet}}": operationName(
      `get_${entitySnake}`,
      `/${feature}/{${entitySnake}_id}`,
      "get",
    ),
    "{{opCreate}}": operationName(`create_${entitySnake}`, `/${feature}`, "post"),
    "{{opUpdate}}": operationName(
      `update_${entitySnake}`,
      `/${feature}/{${entitySnake}_id}`,
      "patch",
    ),
    "{{domain_fields}}": indent(
      fields.map((f) => `${f.camel}: ${f.kind}${f.nullable ? " | null" : ""};`),
      2,
    ),
    "{{zod_create_fields}}": indent(
      fields.map((f) => `${f.camel}: ${zodExpression(f)},`),
      2,
    ),
    "{{zod_update_fields}}": indent(
      fields.map((f) => `${f.camel}: ${zodExpression(f)},`),
      2,
    ),
    "{{mapper_fields}}": indent(
      fields.map((f) => `${f.camel}: dto.${f.snake},`),
      4,
    ),
    "{{mapper_test_assertions}}": indent(
      fields.map((f) => `expect(${camel(entityFile)}.${f.camel}).toBe(dto.${f.snake});`),
      4,
    ),
    "{{create_dto_fields}}": indent(
      fields.map((f) => `${f.snake}: values.${f.camel},`),
      10,
    ),
    "{{factory_dto_fields}}": indent(
      fields.map((f) => `${f.snake}: ${sample(f, 0)},`),
      4,
    ),
    "{{factory_domain_fields}}": indent(
      fields.map((f) => `${f.camel}: ${sample(f, 0)},`),
      4,
    ),
    "{{table_headers}}": indent(
      fields.map(
        (f) =>
          `<th scope="col" className="py-2 font-medium">\n  ${f.label}\n</th>`,
      ),
      16,
    ),
    "{{table_cells}}": indent(
      fields.map((f) => `<td className="py-2 text-gray-700">{${cellExpression(f)}}</td>`),
      18,
    ),
    "{{valid_form_literal}}": validLiteral,
    "{{invalid_form_literal}}": invalidLiteral,
    "{{invalid_field_test}}": invalidTest,
    "{{first_field_label}}": fields[0].label,
    "{{first_field_camel}}": words(fields[0].camel),
  };
}

function render(templatePath, values) {
  let text = readFileSync(join(TEMPLATE_ROOT, templatePath), "utf8");
  for (const key of Object.keys(values).sort((a, b) => b.length - a.length)) {
    text = text.split(key).join(values[key]);
  }
  return text;
}

function buildPlan(feature, entity, fields) {
  const values = substitutions(feature, entity, fields);
  const entityFile = values["{{entity-file}}"];
  const base = `frontend/src/features/${feature}`;
  const route = `frontend/src/app/(app)/${feature}`;
  return {
    [`${base}/model/${entityFile}.ts`]: render("model/entity.ts.tmpl", values),
    [`${base}/model/${entityFile}-schema.ts`]: render("model/entity-schema.ts.tmpl", values),
    [`${base}/model/${entityFile}-schema.test.ts`]: render(
      "model/entity-schema.test.ts.tmpl",
      values,
    ),
    [`${base}/model/${entityFile}-filters.ts`]: render("model/entity-filters.ts.tmpl", values),
    [`${base}/model/${entityFile}-filters.test.ts`]: render(
      "model/entity-filters.test.ts.tmpl",
      values,
    ),
    [`${base}/api/${entityFile}-mapper.ts`]: render("api/entity-mapper.ts.tmpl", values),
    [`${base}/api/${entityFile}-mapper.test.ts`]: render(
      "api/entity-mapper.test.ts.tmpl",
      values,
    ),
    [`${base}/api/${entityFile}-queries.ts`]: render("api/entity-queries.ts.tmpl", values),
    [`${base}/api/use-create-${entityFile}.ts`]: render(
      "api/use-create-entity.ts.tmpl",
      values,
    ),
    [`${base}/hooks/use-${feature}-filters.ts`]: render(
      "hooks/use-feature-filters.ts.tmpl",
      values,
    ),
    [`${base}/hooks/use-${feature}-filters.test.ts`]: render(
      "hooks/use-feature-filters.test.ts.tmpl",
      values,
    ),
    [`${base}/components/${feature}-list-view.tsx`]: render(
      "components/feature-list-view.tsx.tmpl",
      values,
    ),
    [`${base}/components/${feature}-list-view.test.tsx`]: render(
      "components/feature-list-view.test.tsx.tmpl",
      values,
    ),
    [`${base}/containers/${feature}-list-page.tsx`]: render(
      "containers/feature-list-page.tsx.tmpl",
      values,
    ),
    [`${base}/containers/${feature}-list-page.test.tsx`]: render(
      "containers/feature-list-page.test.tsx.tmpl",
      values,
    ),
    [`${base}/server/fetch-${feature}-page.ts`]: render(
      "server/fetch-feature-page.ts.tmpl",
      values,
    ),
    [`${base}/testing/factories.ts`]: render("testing/factories.ts.tmpl", values),
    [`${route}/page.tsx`]: render("route/page.tsx.tmpl", values),
    [`${route}/loading.tsx`]: render("route/loading.tsx.tmpl", values),
    [`${route}/error.tsx`]: render("route/error.tsx.tmpl", values),
  };
}

function validatePaths(paths, feature, approvedFile) {
  const args = [VALIDATOR, "--proposed", "-", "--feature", feature];
  if (approvedFile) args.push("--approved", approvedFile);
  const result = spawnSync("python3", args, {
    input: paths.join("\n"),
    encoding: "utf8",
  });
  if (result.status !== 0) {
    process.stderr.write((result.stdout ?? "") + (result.stderr ?? ""));
    process.exit(1);
  }
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  if (!options.feature || !options.entity) fail(USAGE);
  if (options.plan === options.apply) fail("choose exactly one of --plan or --apply");
  if (!/^[a-z][a-z0-9-]*$/.test(options.feature)) {
    fail(`feature ${options.feature} must be kebab-case`);
  }
  if (!/^[A-Z][A-Za-z0-9]*$/.test(options.entity)) {
    fail(`entity ${options.entity} must be PascalCase`);
  }
  if (options.fields.length === 0) fail("at least one --field name:type is required");

  const fields = options.fields.map((raw) => parseField(raw, options.nullable));
  const plan = buildPlan(options.feature, options.entity, fields);
  const paths = Object.keys(plan).sort();
  const followUp = [
    "cd frontend && npm run generate:api",
    "cd frontend && npm run lint && npm run typecheck && npm run test:fast",
  ];

  validatePaths(paths, options.feature, undefined);

  if (options.plan) {
    process.stdout.write(
      `${JSON.stringify(
        {
          feature: options.feature,
          entity: options.entity,
          artifacts: paths,
          approved_list: paths,
          generated_client: {
            module: `frontend/src/lib/api/generated/endpoints/${options.feature}/${options.feature}.ts`,
            functions: [
              substitutions(options.feature, options.entity, fields)["{{opList}}"],
              substitutions(options.feature, options.entity, fields)["{{opGet}}"],
              substitutions(options.feature, options.entity, fields)["{{opCreate}}"],
            ],
            note: "run generate:api after the backend slice exists; typecheck proves the names",
          },
          follow_up: followUp,
        },
        null,
        2,
      )}\n`,
    );
    return;
  }

  if (!options.approved) fail("--apply requires --approved <path-list-file>");
  validatePaths(paths, options.feature, options.approved);

  const root = repoRoot();
  for (const path of paths) {
    const target = join(root, path);
    mkdirSync(dirname(target), { recursive: true });
    writeFileSync(target, plan[path], "utf8");
  }

  const frontend = join(root, "frontend");
  spawnSync("npx", ["prettier", "--write", ...paths.map((p) => p.replace("frontend/", ""))], {
    cwd: frontend,
    encoding: "utf8",
  });

  process.stdout.write(
    `${JSON.stringify({ written: paths, follow_up: followUp }, null, 2)}\n`,
  );
}

main();
