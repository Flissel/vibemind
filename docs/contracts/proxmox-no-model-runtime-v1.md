# Proxmox No-Model Runtime V1

## Invariant

No model may execute on the Proxmox host or in any VM, container, service,
worker, or job scheduled on it.

This prohibition covers LLM, embedding, reranking, OCR and vision, speech
recognition, TTS, lip-sync, image, video, and any other model inference. Model
weights, model caches, accelerators assigned for inference, and model-serving
runtimes are forbidden inside the Proxmox boundary.

The rule applies regardless of model size, quantization, provider-compatible
API shape, CPU/GPU/NPU execution, container image, or whether the process is
described as a helper, agent, worker, fallback, or development service.

## Permitted boundary

Proxmox may host data and application infrastructure such as databases, object
storage, queues, workflow engines, gateways, observability, and deterministic
tools that perform no model inference.

Brain, OpenFang, Spaces, and workers may run there only when they perform no
inference and route every model request to an approved provider outside the
Proxmox boundary; missing remote authority fails closed. They must not download,
mount, cache, load, or serve model weights and must not fall back to a local
model when the external provider is unavailable.

Provider model identifiers such as `EMBEDDING_MODEL` are configuration only and
never authorize local weights or inference. A remote provider request is
permitted only when the actual model process executes outside the Proxmox host
and all of its guests.

## Deployment consequence

Every Proxmox deployment manifest must remain free of model-server services,
model-runtime images or commands, model-weight/cache mounts, and inference
accelerator assignments. A violation blocks deployment readiness. Reachability,
available CPU/GPU capacity, or an existing container never overrides this rule.
