import { titleCase } from "./format.js";

export function greet(name) {
  return `Hello, ${titleCase(name)}!`;
}
