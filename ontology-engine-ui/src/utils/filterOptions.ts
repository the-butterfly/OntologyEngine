// src/utils/filterOptions.ts
// Shared filter option utilities

/**
 * Case-insensitive filter function for antd Select components
 */
export const caseInsensitiveFilter = (input: string, option: { label?: string } | unknown) => {
  const label = (option as { label?: string })?.label ?? '';
  return label.toLowerCase().includes(input.toLowerCase());
};
