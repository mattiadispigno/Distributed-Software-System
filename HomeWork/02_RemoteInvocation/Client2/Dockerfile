# syntax=docker/dockerfile:1

FROM eclipse-temurin:21-jre as base

FROM eclipse-temurin:21-jdk as build
WORKDIR /src
COPY . .
COPY --from=proto greeter.proto app/src/main/proto/greeter.proto
RUN --mount=type=cache,target=/root/.gradle \
    ./gradlew :app:installDist --no-daemon

FROM base AS final

ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "${UID}" \
    appuser
USER appuser

COPY --from=build /src/app/build/install/app /app

ENTRYPOINT [ "/app/bin/app" ]
