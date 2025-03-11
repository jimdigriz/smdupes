Image Deduplicator for [SmugMug](https://smugmug.com/).

I was looking for a tool to deduplicate images on my SmugMug account (~45k images), and I wanted it to work like [`jdupes`](https://www.jdupes.com/) and be fast.

**N.B.** this is a Works In Progress...

## Related Links

 * [SmugMug API v2](https://api.smugmug.com/api/v2/doc/index.html)
 * [MugMatch](https://github.com/AndrewsOR/MugMatch) - really helpful tool for remove duplicates
    * comes with a GUI
    * ...really slow
    * quite neat the default rules on what to delete

# Preflight

Run the following to start off with:

    python3 -m venv .venv
    ./.venv/bin/pip install -r requirements.txt
    cp conf.ini.example conf.ini

Create an [API key](https://api.smugmug.com/api/v2/doc/tutorial/api-key.html) and edit `conf.ini` with the values of your API client id and client secret.

# Usage

The tool has two phases:

 1. build list of duplicates for review
 1. consume list of images to delete

If you have not logged in yet, your first run will include a login session where:

 1. your web browser opens SmugMug and asks you to log in
 1. after logging in, you will be provided with a code to type into this tool
 1. after typing in the code, the tool will cache the access tokens in `conf.ini`

To build a list of duplicates run:

    ./.venv/bin/python smdupes.py

This builds a `db.sqlite3` file, for me this takes roughly one minute for 50,000 images.

Once built, open it with:

    sqlite3 db.sqlite3

To list the duplicates (keeping the old with the oldest creation timestamp) execute:

    WITH v AS (
      SELECT
        *, ROW_NUMBER() OVER (PARTITION BY md5 ORDER BY created ASC) i
      FROM image
    )
    SELECT name, filename, v.uri
    FROM v
    JOIN album a ON a.uri = v.album
    WHERE i > 1;
