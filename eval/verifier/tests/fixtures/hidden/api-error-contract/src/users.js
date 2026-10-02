const users = new Map([["u_1", { id: "u_1", name: "Ada" }]]);

const failure = (status, code, message) => ({ status, body: { code, message } });

export function handleUserLookup(request) {
  const id = request.query.id;
  if (!id) return failure(400, "missing_user_id", "Query parameter id is required.");
  const user = users.get(id);
  if (!user) return failure(404, "user_not_found", "No user has that id.");
  return { status: 200, body: user };
}
