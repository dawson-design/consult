// Applies a user's widget settings change to a dashboard being edited.
export function updateWidget(dashboard, widgetId, changes) {
  const widget = dashboard.widgets.find((w) => w.id === widgetId);
  if (!widget) throw new Error(`unknown widget ${widgetId}`);
  Object.assign(widget.config, changes);
  return dashboard;
}
