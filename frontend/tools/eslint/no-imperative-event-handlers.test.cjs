const { RuleTester } = require("eslint");
const rule = require("./no-imperative-event-handlers.cjs");

const ruleTester = new RuleTester({
  languageOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
    parserOptions: { ecmaFeatures: { jsx: true } },
  },
});

ruleTester.run("no-imperative-event-handlers", rule, {
  valid: [
    'function View({ onNavigate }) { return <button onClick={() => onNavigate("week")} />; }',
    "function View({ onOpen }) { return <button onClick={onOpen} />; }",
    "function View({ onOpen }) { return <button {...{ onClick: onOpen }} />; }",
    "function View(props) { return <button {...props} />; }",
    "function View(props) { return <button onClick={props.onOpen} />; }",
    "function View({ onNavigate, rows }) { return <>{rows.map((row) => <button onClick={() => onNavigate(row.id)} />)}</>; }",
  ],
  invalid: [
    {
      code: "function View() { return <button {...{ onClick: () => window.alert('x') }} />; }",
      errors: [{ messageId: "imperative" }],
    },
    {
      code: "function View() { return <button onClick={() => alert('nope')} />; }",
      errors: [{ messageId: "imperative" }],
    },
    {
      code: "function View({ onNavigate }) { const handleClick = () => onNavigate('week'); return <button onClick={handleClick} />; }",
      errors: [{ messageId: "imperative" }],
    },
    {
      code: "function View({ onNavigate }) { return <button onClick={() => { onNavigate('week'); alert('nope'); }} />; }",
      errors: [{ messageId: "imperative" }],
    },
    {
      code: "function View({ onNavigate }) { return <button onClick={externalHandler} />; }",
      errors: [{ messageId: "imperative" }],
    },
    {
      code: "const onSave = () => alert('nope'); function View() { return <button onClick={onSave} />; }",
      errors: [{ messageId: "imperative" }],
    },
  ],
});
