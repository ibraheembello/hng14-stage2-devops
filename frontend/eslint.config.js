// ESLint flat config for the frontend service.
//
// Kept deliberately small: language options for Node 20 CommonJS
// plus the recommended rule set. Extend rules here as the codebase
// grows.
const globals = require("globals");

module.exports = [
  {
    files: ["**/*.js"],
    ignores: ["node_modules/**", "views/**"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "commonjs",
      globals: { ...globals.node },
    },
    rules: {
      "no-unused-vars": [
        "warn",
        {
          argsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],
      "no-undef": "error",
      "no-console": "off",
      "semi": ["error", "always"],
      "eqeqeq": ["error", "always"],
    },
  },
];
