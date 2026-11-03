FROM golang:1.27 AS build
WORKDIR /src
COPY api/go.mod api/go.sum ./
RUN go mod download
COPY api/ ./
ARG GIT_SHA=unknown
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w -X main.version=$GIT_SHA -X main.built=$(date -u +%Y-%m-%dT%H:%M:%SZ)" -o /server ./cmd/server

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /server /server
EXPOSE 8080
ENTRYPOINT ["/server"]
