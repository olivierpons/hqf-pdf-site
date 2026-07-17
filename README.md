# hqf-pdf-site

Sign-up and billing website for the hqf-pdf rendering service.

A Django application where a customer creates an account, gets an API key, and
pays for the PDF rendering service. It is the only place that writes the render
server's client configuration: a customer's plan and rights land in the TOML
file the server reads.

## Scope

This repository holds the website only. It is deliberately separate from:

- **hqf-pdf** — the PDF engine (Rust library, sold under a perpetual licence).
- **hqf-pdf-server** — the rendering server that answers render requests.

## Status

Early. Nothing here is deployed yet.

## Licence

None published. All rights reserved.
