ARG BUILD_FROM
FROM ${BUILD_FROM}

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# hue-entertainment zieht native Krypto-/DTLS-Abhängigkeiten nach, die auf
# musl u. U. aus dem Quelltext gebaut werden müssen. Build-Toolchain nur für
# die Installation einspielen und danach wieder entfernen; die Runtime-Libs
# (libffi, openssl, mbedtls) bleiben.
RUN apk add --no-cache libffi openssl mbedtls curl \
    && apk add --no-cache --virtual .build-deps \
        build-base python3-dev libffi-dev openssl-dev mbedtls-dev cargo

COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt \
    && apk del .build-deps

# App-Code und s6-Service (rootfs/app -> /app, rootfs/etc -> /etc)
COPY rootfs /

RUN chmod a+x /etc/s6-overlay/s6-rc.d/redalert/run \
              /etc/s6-overlay/s6-rc.d/redalert/finish

LABEL \
    io.hass.name="Red Alert Entertainment" \
    io.hass.description="Hue-Entertainment-Lauflicht (Star Trek Alarmstufe Rot)" \
    io.hass.type="addon" \
    io.hass.version="1.1.3"

# Ersetzt die (obsolete) config.yaml-Option `watchdog`: Supervisor wertet den
# Container-Health-Status aus und startet bei Bedarf neu.
HEALTHCHECK --start-period=30s --interval=30s --timeout=10s --retries=3 \
    CMD curl -fsS http://localhost:8099/health || exit 1

# Kein CMD: s6-overlay der HA-Basis startet den Dienst über den redalert-Service.
