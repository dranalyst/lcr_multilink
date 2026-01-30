import os
from sqlalchemy import create_engine, text
from utils.phone_country_enrich import enrich_msisdn

def main():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL not set (did you source .env?)")

    engine = create_engine(db_url, future=True)

    select_sql = text("""
        SELECT gw_name, gw_slot, msisdn
        FROM public.af_gateways
        WHERE msisdn IS NOT NULL AND msisdn <> ''
          AND (
            country_iso2 = '--'
            OR country_name = 'Unknown'
            OR country_dial_code = '+++'
            OR operator_name = 'Unknown'
          )
    """)

    # One transaction for everything (no nested begin)
    with engine.begin() as conn:
        rows = []
        for gw_name, gw_slot, msisdn in conn.execute(select_sql):
            iso2, cname, dial, op = enrich_msisdn(msisdn)
            rows.append((gw_name, gw_slot, iso2, cname, dial, op))

        if not rows:
            print("af_gateways enrichment: nothing to update")
            return

        values = []
        params = {}
        for i, (gw, slot, iso2, cname, dial, op) in enumerate(rows):
            values.append(f"(:gw_{i}, :slot_{i}, :iso2_{i}, :cname_{i}, :dial_{i}, :op_{i})")
            params.update({
                f"gw_{i}": gw,
                f"slot_{i}": slot,
                f"iso2_{i}": iso2,
                f"cname_{i}": cname,
                f"dial_{i}": dial,
                f"op_{i}": op,
            })

        update_sql = text(f"""
            UPDATE public.af_gateways a
            SET
              country_iso2 = v.country_iso2,
              country_name = v.country_name,
              country_dial_code = v.country_dial_code,
              operator_name = v.operator_name
            FROM (VALUES
              {", ".join(values)}
            ) AS v(gw_name, gw_slot, country_iso2, country_name, country_dial_code, operator_name)
            WHERE a.gw_name = v.gw_name
              AND a.gw_slot = v.gw_slot
        """)

        conn.execute(update_sql, params)

    print(f"af_gateways enrichment: updated {len(rows)} rows")

if __name__ == "__main__":
    main()