// Entry point: reads the environment, opens the database and catalogue, and
// serves the shop front's HTTP API on PORT.
import { loadCatalogue } from "./commissions/catalogue.ts";
import { commissionRoutes } from "./commissions/routes.ts";
import { openDatabase } from "./database.ts";
import { createApp } from "./http/server.ts";
import { patronRoutes } from "./patrons/routes.ts";

const port = Number(process.env.PORT ?? 3000);
const db = openDatabase(process.env.DATABASE_PATH ?? "commissions.db");
const catalogue = loadCatalogue(new URL("../catalogue.json", import.meta.url).pathname);
const ratesUrl = process.env.RATES_URL ?? "http://localhost:9";

createApp([...patronRoutes(db), ...commissionRoutes({ db, catalogue, ratesUrl })]).listen(port);
