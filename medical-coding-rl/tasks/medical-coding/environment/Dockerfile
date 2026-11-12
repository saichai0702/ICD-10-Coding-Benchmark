FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df

# Reference desk: FY2027 public code sets + the codetools lookup CLI.
COPY codetools.py /usr/local/bin/codetools
COPY reference.tar.gz /tmp/reference.tar.gz
RUN chmod +x /usr/local/bin/codetools \
 && mkdir -p /opt/reference \
 && tar -xzf /tmp/reference.tar.gz -C /opt/reference \
 && rm /tmp/reference.tar.gz \
 && codetools build-index
ENV CODING_REF=/opt/reference

# The 36 encounters to code: /app/cases/<CASE_ID>/{chart/*.txt, encounter.json}.
# No answers here: the ground truth lives in solution/ and tests/ only.
COPY cases/ /app/cases/
RUN mkdir -p /app/output
WORKDIR /app
