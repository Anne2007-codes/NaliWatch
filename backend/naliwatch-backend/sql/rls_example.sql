-- OPT-IN example of enforcing access in Postgres as well as in the API.
-- The API sets app.user_id / app.role / app.ward per request (see app/deps.py).
-- Use a NON-owner role for the API, otherwise RLS is bypassed:
--   CREATE ROLE naliwatch_api LOGIN PASSWORD '...';  GRANT ALL ON ALL TABLES IN SCHEMA public TO naliwatch_api;
-- Then point DATABASE_URL at naliwatch_api. Background workers need a role that bypasses RLS (BYPASSRLS).
-- Test this against your own flows before enabling; it is a starting point, not a drop-in.

ALTER TABLE properties ENABLE ROW LEVEL SECURITY;
CREATE POLICY property_access ON properties USING (
  current_setting('app.role', true) = 'admin'
  OR (current_setting('app.role', true) = 'household' AND owner_id = NULLIF(current_setting('app.user_id', true), '')::int)
  OR (current_setting('app.role', true) = 'officer' AND ward = current_setting('app.ward', true))
  OR current_setting('app.role', true) IN ('operator', 'driver')   -- narrowed by job/trip joins in the API
);

ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
CREATE POLICY report_access ON reports USING (
  current_setting('app.role', true) = 'admin'
  OR (current_setting('app.role', true) = 'officer' AND ward = current_setting('app.ward', true))
  OR reporter_id = NULLIF(current_setting('app.user_id', true), '')::int
);

ALTER TABLE flags ENABLE ROW LEVEL SECURITY;
CREATE POLICY flag_access ON flags USING (
  current_setting('app.role', true) = 'admin'
  OR (current_setting('app.role', true) = 'officer' AND ward = current_setting('app.ward', true))
);
