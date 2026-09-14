# Architecture

SP-Farms uses inward-facing dependencies and a single composition root.

## Layers

- `domain`: business entities, value objects, errors, and rules. Depends only on the Python standard library.
- `application`: use cases and ports. Depends on `domain`, never concrete infrastructure or UI.
- `infrastructure`: database, API, device, vault, and operating-system adapters. Implements application ports.
- `modules`: cohesive feature packages assembled from domain, application, and presentation components.
- `plugins`: public extension contracts and plugin loading.
- `app`: PySide6 presentation and process entry points. Calls application services; it does not access persistence or construct adapters.
- `bootstrap.py`: the composition root. It is the only place where concrete infrastructure is wired into application context.

Allowed dependency direction:

```text
app ──> application ──> domain
                    <── infrastructure
bootstrap ──> app + application + infrastructure
```

Cross-layer communication uses explicit application protocols. UI handlers submit work to application services; long-running adapters execute through background jobs introduced by later phases. `ApplicationContext.close()` owns process-level shutdown hooks and invokes them once in reverse registration order.
