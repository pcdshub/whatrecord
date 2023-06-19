export function nullable_string_to_array(value: any): string[] {
  if (value === null || value === undefined) {
    return [];
  }
  if (typeof value == "object") {
    return value;
  }
  return [value];
}
