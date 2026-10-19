These files are NLTK's `punkt_tab` English sentence tokenizer model
(`abbrev_types.txt`, `collocations.tab`, `ortho_context.tab`,
`sent_starters.txt`, plus the upstream `README`), downloaded from NLTK's
`nltk_data` repository (https://github.com/nltk/nltk_data), licensed
Apache-2.0. Only the English model is vendored; other languages aren't
needed by this codebase.

To refresh: `python -m nltk.downloader -d <tmpdir> punkt_tab` and copy
`<tmpdir>/tokenizers/punkt_tab/english/` and
`<tmpdir>/tokenizers/punkt_tab/README` here.
