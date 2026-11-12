const EVENT_PROP = /^on[A-Z]/;

const isFunction = (node) =>
  node &&
  ["ArrowFunctionExpression", "FunctionDeclaration", "FunctionExpression"].includes(node.type);

const isComponentName = (name) => typeof name === "string" && /^[A-Z]/.test(name);

const getFunctionName = (node) => {
  if (node.id?.type === "Identifier") return node.id.name;
  const parent = node.parent;
  if (parent?.type === "VariableDeclarator" && parent.id.type === "Identifier") {
    return parent.id.name;
  }
  if (parent?.type === "AssignmentExpression" && parent.left.type === "Identifier") {
    return parent.left.name;
  }
  return null;
};

const getComponentFunction = (node) => {
  const functions = [];
  for (let current = node.parent; current; current = current.parent) {
    if (isFunction(current)) functions.push(current);
  }
  return functions.find((current) => isComponentName(getFunctionName(current))) ?? functions.at(-1);
};

const getPatternIdentifier = (pattern) => {
  if (pattern?.type === "Identifier") return pattern;
  if (pattern?.type === "AssignmentPattern") return getPatternIdentifier(pattern.left);
  return null;
};

const getComponentProps = (component) => {
  const callbackNames = new Set();
  const propObjects = new Set();
  const parameter = component?.params[0];
  if (!parameter) return { callbackNames, propObjects };

  if (parameter.type === "Identifier") {
    propObjects.add(parameter.name);
    return { callbackNames, propObjects };
  }

  if (parameter.type !== "ObjectPattern") return { callbackNames, propObjects };

  for (const property of parameter.properties) {
    if (property.type !== "Property" || property.computed) continue;
    const key = property.key.type === "Identifier" ? property.key.name : property.key.value;
    if (!EVENT_PROP.test(key)) continue;
    const value = getPatternIdentifier(property.value);
    if (value) callbackNames.add(value.name);
  }
  return { callbackNames, propObjects };
};

const isPropMember = (node, props) => {
  if (node.type !== "MemberExpression" || node.object.type !== "Identifier") return false;
  if (!props.propObjects.has(node.object.name)) return false;
  if (node.computed)
    return typeof node.property.value === "string" && EVENT_PROP.test(node.property.value);
  return node.property.type === "Identifier" && EVENT_PROP.test(node.property.name);
};

const isCallbackReference = (node, props) => {
  if (node.type === "Identifier") return props.callbackNames.has(node.name);
  return isPropMember(node, props);
};

const collectCalls = (node, calls = []) => {
  if (!node || typeof node !== "object") return calls;
  if (node.type === "CallExpression") calls.push(node);
  for (const [key, value] of Object.entries(node)) {
    if (
      key === "parent" ||
      key === "tokens" ||
      key === "comments" ||
      key === "loc" ||
      key === "range"
    ) {
      continue;
    }
    if (Array.isArray(value)) {
      for (const child of value) collectCalls(child, calls);
    } else if (value && typeof value === "object") {
      collectCalls(value, calls);
    }
  }
  return calls;
};

const isDelegatingHandler = (node, props) => {
  if (!["ArrowFunctionExpression", "FunctionExpression"].includes(node.type)) return false;
  const calls = collectCalls(node.body);
  return calls.length > 0 && calls.every((call) => isCallbackReference(call.callee, props));
};

module.exports = {
  meta: {
    type: "problem",
    docs: {
      description: "Allow feature views to forward callback props without owning event behavior.",
    },
    schema: [],
    messages: {
      imperative:
        "Feature components may only forward callback props; move event behavior to the container.",
    },
  },
  create(context) {
    const componentProps = new WeakMap();

    const getProps = (component) => {
      if (!componentProps.has(component))
        componentProps.set(component, getComponentProps(component));
      return componentProps.get(component);
    };

    return {
      JSXAttribute(node) {
        if (node.name.type !== "JSXIdentifier" || !EVENT_PROP.test(node.name.name)) return;
        const component = getComponentFunction(node);
        if (!component) return;
        const expression =
          node.value?.type === "JSXExpressionContainer" ? node.value.expression : null;
        const props = getProps(component);
        const allowed =
          expression && (expression.type === "Identifier" || expression.type === "MemberExpression")
            ? isCallbackReference(expression, props)
            : expression && isDelegatingHandler(expression, props);
        if (!allowed) context.report({ node, messageId: "imperative" });
      },
    };
  },
};
