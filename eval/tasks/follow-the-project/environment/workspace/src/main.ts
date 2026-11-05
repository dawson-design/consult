// Entry point: serves the API on PORT.
import { buildServer } from "./server.ts";

buildServer().listen(Number(process.env.PORT ?? 3000));
