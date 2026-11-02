#!/bin/bash
# Oracle: native semantics only. A visible <label> tied to a required email
# input, a real submit button, and a status paragraph that is a polite live
# region from page load. The form's submit event (which the browser fires
# only once the native email validation passes, by button or by Enter)
# prevents the reload and writes the success text with textContent. No test
# is added: Node has no DOM here, a DOM library would be a new dependency,
# and asserting the markup's text proves nothing about behavior, so keyboard
# and screen-reader checks stay as named manual gaps in the report.
set -euo pipefail
cd /app
cat > public/index.html <<'HTML'
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Subscribe</title>
  </head>
  <body>
    <form id="subscribe-form">
      <label for="email">Email address</label>
      <input id="email" name="email" type="email" autocomplete="email" required>
      <button type="submit">Subscribe</button>
      <p id="status" role="status"></p>
    </form>
    <script>
      const form = document.getElementById("subscribe-form");
      const status = document.getElementById("status");
      // The browser fires submit only after the required email field passes
      // its native validation, so an empty or malformed address never gets here.
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        status.textContent = "Subscribed";
      });
    </script>
  </body>
</html>
HTML
