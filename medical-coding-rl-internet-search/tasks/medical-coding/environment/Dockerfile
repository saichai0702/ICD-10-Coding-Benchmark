FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df

# Internet-search variant: no reference bundle and no codetools in the image.
# The agent finds and downloads the public FY2027 code sets itself (task.toml: network_mode = "public").
# These tools let it fetch and unpack them (CMS ships zip / XML / PDF / text files).
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl wget unzip poppler-utils \
 && rm -rf /var/lib/apt/lists/*

# The 36 encounters to code: /app/cases/<CASE_ID>/{chart/*.txt, encounter.json}.
# No answers here: the ground truth lives in solution/ and tests/ only.
COPY cases/ /app/cases/
RUN mkdir -p /app/output /app/reference
WORKDIR /app
