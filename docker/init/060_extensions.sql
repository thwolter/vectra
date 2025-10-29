\set ON_ERROR_STOP on

DO $extensions$
BEGIN
  PERFORM d.extname
  FROM pg_extension d
  WHERE d.extname = 'pgcrypto';
  IF NOT FOUND THEN
    EXECUTE 'CREATE EXTENSION pgcrypto';
  END IF;

  PERFORM d.extname
  FROM pg_extension d
  WHERE d.extname = 'vector';
  IF NOT FOUND THEN
    EXECUTE 'CREATE EXTENSION vector';
  END IF;
END;
$extensions$ LANGUAGE plpgsql;
