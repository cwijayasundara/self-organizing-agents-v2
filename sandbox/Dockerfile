FROM python:3.12-slim@sha256:12316debbfb86890f6b2d825820612741ba527ad5a44e3902759141d572bfe8f
COPY sandbox/requirements.lock /opt/agora-rlms-requirements.lock
RUN pip install --no-cache-dir -r /opt/agora-rlms-requirements.lock \
    && printf '%s\n' 'd04208afbad29ca675ab13478c40ee8bebc84bfe' > /opt/agora-rlms-revision \
    && pip freeze > /opt/agora-rlms-dependencies.txt
LABEL ai.agora.rlm-revision="d04208afbad29ca675ab13478c40ee8bebc84bfe"
USER 65534:65534
WORKDIR /scratch
