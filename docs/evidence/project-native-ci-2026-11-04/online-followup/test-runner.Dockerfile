FROM python:3.12-slim AS python_runtime
FROM postgres:16
COPY --from=python_runtime /usr/local/ /usr/local/
COPY --from=python_runtime /usr/lib/x86_64-linux-gnu/libsqlite3.so.* /usr/lib/x86_64-linux-gnu/
COPY wheels /wheels
COPY requirements.lock /requirements.lock
RUN ldconfig && python -c "import ssl,sqlite3,ctypes,lzma,bz2,xml.parsers.expat" && python -m pip install --disable-pip-version-check --no-index --find-links=/wheels -r /requirements.lock && python -m pip check && rm -rf /wheels
COPY --chown=postgres:postgres source/ /work/
COPY --chown=postgres:postgres caddy/caddy /work/caddy
WORKDIR /work
ENV HOME=/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/work/backend
USER postgres
ENTRYPOINT ["/usr/local/bin/python"]
