// Copies a dashboard for storage so later edits to the live object do not
// leak into what was saved.
export function snapshot(dashboard) {
  return {
    ...dashboard,
    widgets: dashboard.widgets.map((widget) => ({ ...widget })),
  };
}
