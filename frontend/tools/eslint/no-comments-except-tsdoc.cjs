const DIRECTIVE =
  /^\s*(eslint\b|eslint-disable|eslint-enable|eslint-env|globals\b|exported\b|prettier-ignore|@ts-expect-error|@ts-ignore|@ts-nocheck|@jsxImportSource|v8 ignore|c8 ignore|istanbul ignore|webpackChunkName|@vitest-environment)/;

const EXPORT_TYPES = new Set([
  "ExportNamedDeclaration",
  "ExportDefaultDeclaration",
  "ExportAllDeclaration",
  "TSExportAssignment",
]);

const DOCUMENTABLE = new Set([
  "FunctionDeclaration",
  "ClassDeclaration",
  "VariableDeclaration",
  "TSInterfaceDeclaration",
  "TSTypeAliasDeclaration",
  "TSEnumDeclaration",
  "TSDeclareFunction",
  "TSPropertySignature",
  "TSMethodSignature",
  "TSEnumMember",
  "PropertyDefinition",
  "MethodDefinition",
]);

module.exports = {
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow every comment except a TSDoc block documenting an exported declaration or one of its members.",
    },
    schema: [],
    messages: {
      banned: "Comments are not allowed. Express intent through naming and structure.",
      misplaced:
        "A /** */ TSDoc block is only allowed directly above an exported declaration or one of its members.",
    },
  },
  create(context) {
    const sourceCode = context.sourceCode ?? context.getSourceCode();

    const isUnderExport = (node) => {
      for (let current = node; current; current = current.parent) {
        if (EXPORT_TYPES.has(current.type)) return true;
        if (current.type === "Program") return false;
      }
      return false;
    };

    const documentsAnExport = (comment) => {
      const token = sourceCode.getTokenAfter(comment, { includeComments: false });
      if (!token) return false;
      let node = sourceCode.getNodeByRangeIndex(token.range[0]);
      if (!node) return false;
      while (
        node.parent &&
        node.parent.type !== "Program" &&
        node.parent.range[0] === node.range[0]
      ) {
        node = node.parent;
      }
      if (!sourceCode.getCommentsBefore(node).includes(comment)) return false;
      if (EXPORT_TYPES.has(node.type)) return true;
      return DOCUMENTABLE.has(node.type) && isUnderExport(node);
    };

    return {
      "Program:exit"() {
        for (const comment of sourceCode.getAllComments()) {
          if (DIRECTIVE.test(comment.value)) continue;
          const isTsdoc = comment.type === "Block" && comment.value.startsWith("*");
          if (isTsdoc && documentsAnExport(comment)) continue;
          context.report({
            loc: comment.loc,
            messageId: isTsdoc ? "misplaced" : "banned",
          });
        }
      },
    };
  },
};
