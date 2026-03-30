"""Anonymize a TMG SQZ backup file for use as a test fixture.

Reads the source SQZ, replaces all personal data with predictable synthetic
values (keeping every structural field — recnos, dsids, relationships —
intact), removes PICS photos, and writes a new SQZ.

Usage:
    python3 tests/anonymize_sqz.py <input.sqz> <output.sqz>

Synthetic value scheme (deterministic, so tests can assert specific values):
    Names       : surname  = "FAMILY<nper>",  given = "Person<nper>"
                  SRNAMEDISP = "FAMILY<nper>, Person<nper>"
    Name dict   : "Name<uid>"
    Place dict  : "Place<uid>"
    Event memos : ""  (cleared)
    Source title: "Source<majnum>"
    Source info : $!& separators kept, all values cleared
    Source text/forms/reminders: ""  (cleared)
    Repo name   : "Repository<recno>";  address/note: ""
    Citation memo/page: ""  (cleared)
    Exhibit name: "Exhibit<idexhibit>";  filenames: ""
    PICS/       : removed entirely
"""

import os
import sys
import shutil
import tempfile
import zipfile

import dbf


def _pad(value, width):
    return value[:width].ljust(width)


def _find(base, suffix, optional=False):
    """Return the path of the unique file in *base* whose name ends with *suffix*.

    Returns None when *optional* is True and no matching file exists.
    """
    suffix_lo = suffix.lower()
    matches = [
        os.path.join(base, fn)
        for fn in os.listdir(base)
        if fn.lower().endswith(suffix_lo)
    ]
    if not matches:
        if optional:
            return None
        raise FileNotFoundError(f"No file ending with {suffix!r} in {base}")
    if len(matches) > 1:
        raise FileNotFoundError(
            f"Multiple files ending with {suffix!r} in {base}: {matches}")
    return matches[0]


def _rw(path):
    """Open a VFP table read-write and return it (caller must close)."""
    t = dbf.Table(path, dbf_type='vfp')
    t.open(dbf.READ_WRITE)
    return t


def anonymize_names(base):
    t = _rw(_find(base, '_n.dbf'))
    try:
        for record in t:
            nper    = record.nper
            surname = f'FAMILY{nper}'
            given   = f'Person{nper}'
            disp    = f'{surname}, {given}'
            with record:
                record.srnamedisp = _pad(disp,         len(record.srnamedisp))
                record.srnamesort = _pad(disp.upper(), len(record.srnamesort))
                record.gvnamesort = _pad(
                    f'{given.upper()} {surname.upper()}',
                    len(record.gvnamesort))
    finally:
        t.close()


def anonymize_name_dict(base):
    t = _rw(_find(base, '_nd.dbf'))
    try:
        for record in t:
            with record:
                record.value = _pad(f'Name{record.uid}', len(record.value))
    finally:
        t.close()


def anonymize_place_dict(base):
    path = _find(base, '_pd.dbf', optional=True)
    if path is None:
        return
    t = _rw(path)
    try:
        for record in t:
            with record:
                record.value = _pad(f'Place{record.uid}', len(record.value))
    finally:
        t.close()


def anonymize_events(base):
    """_g.dbf: clear EFOOT for regular events; keep a placeholder for Note-type
    events so import_notes still creates Note objects in tests."""
    note_etypes = set()
    tt = dbf.Table(_find(base, '_t.dbf'), dbf_type='vfp')
    with tt:
        for r in tt:
            if r.etypename.strip() == 'Note':
                note_etypes.add(r.etypenum)

    t = _rw(_find(base, '_g.dbf'))
    try:
        for record in t:
            with record:
                if record.etype in note_etypes:
                    record.efoot = f'Note text {record.recno}'
                else:
                    record.efoot = ''
    finally:
        t.close()


def anonymize_sources(base):
    path = _find(base, '_m.dbf', optional=True)
    if path is None:
        return
    t = _rw(path)
    try:
        for record in t:
            # Keep $!& separators so positional parsing still works
            info_raw  = record.info or ''
            anon_info = '$!&'.join('' for _ in info_raw.split('$!&'))
            with record:
                record.title     = _pad(f'Source{record.majnum}', len(record.title))
                record.info      = anon_info
                record.text      = ''
                record.fform     = ''
                record.sform     = ''
                record.bform     = ''
                record.reminders = ''
    finally:
        t.close()


def anonymize_repos(base):
    path = _find(base, '_r.dbf', optional=True)
    if path is None:
        return
    t = _rw(path)
    try:
        for record in t:
            with record:
                record.name  = _pad(f'Repository{record.recno}', len(record.name))
                record.rnote = ''
    finally:
        t.close()


def anonymize_citations(base):
    path = _find(base, '_s.dbf', optional=True)
    if path is None:
        return
    t = _rw(path)
    try:
        for record in t:
            with record:
                record.subsource = ''
                record.citmemo   = ''
    finally:
        t.close()


def anonymize_exhibits(base):
    path = _find(base, '_i.dbf', optional=True)
    if path is None:
        return
    t = _rw(path)
    try:
        for record in t:
            with record:
                record.xname     = _pad(f'Exhibit{record.idexhibit}', len(record.xname))
                record.vfilename = ''
                record.ifilename = ''
    finally:
        t.close()


def remove_pics(base):
    pics = os.path.join(base, 'pics')
    if os.path.isdir(pics):
        shutil.rmtree(pics)


def repack(base, parent_dir, output_sqz):
    with zipfile.ZipFile(output_sqz, 'w', zipfile.ZIP_DEFLATED) as zout:
        for dirpath, _, files in os.walk(base):
            for fn in files:
                full = os.path.join(dirpath, fn)
                arc  = os.path.relpath(full, parent_dir).replace('\\', '/')
                zout.write(full, arc)
    print(f'Written: {output_sqz}')


def main(input_sqz, output_sqz):
    tmpdir = tempfile.mkdtemp(prefix='tmg_anon_')
    try:
        print(f'Extracting {input_sqz} ...')
        with zipfile.ZipFile(input_sqz) as z:
            z.extractall(tmpdir)

        # Find the directory containing the .pjc file
        base = None
        for dirpath, _, files in os.walk(tmpdir):
            if any(f.lower().endswith('.pjc') for f in files):
                base = dirpath
                break
        if not base:
            raise FileNotFoundError("No .pjc file found in archive")

        # Lowercase all filenames (mirrors what libtmg does at runtime)
        for fn in os.listdir(base):
            lo = fn.lower()
            if fn != lo:
                os.rename(os.path.join(base, fn), os.path.join(base, lo))

        steps = [
            ('names',            anonymize_names),
            ('name dictionary',  anonymize_name_dict),
            ('place dictionary', anonymize_place_dict),
            ('event memos',      anonymize_events),
            ('sources',          anonymize_sources),
            ('repositories',     anonymize_repos),
            ('citations',        anonymize_citations),
            ('exhibits',         anonymize_exhibits),
            ('PICS',             remove_pics),
        ]
        for label, fn in steps:
            print(f'Anonymizing {label} ...')
            fn(base)

        print('Repacking ...')
        repack(base, tmpdir, output_sqz)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f'Usage: {sys.argv[0]} <input.sqz> <output.sqz>')
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
