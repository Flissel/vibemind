---
name: {name}
slug: {slug}
type: coding-project
code_path: {code_path}
stack:
  language: {stack_language}
  framework: {stack_framework}
  package_manager: {stack_pkg}
git:
  remote: {git_remote}
  branch: {git_branch}
  last_commit: {git_last_commit}
deployment:
  provider: {deploy_provider}
  url: {deploy_url}
  env_vars_secret_path: {deploy_secrets}
tags: {tags}
created_at: {created_at}
status: active
aliases: {aliases}
---

# {name}

> **Wo liegt der Code?** [`{code_path}`]({code_path})

## Steckbrief
- **Sprache / Framework:** {stack_language} {stack_framework}
- **Paket-Manager:** {stack_pkg}
- **Tags:** {tags_human}
- **Status:** active
- **Erstellt:** {created_at}

## Beschreibung
{description}

## Git
- **Remote:** {git_remote}
- **Aktueller Branch:** {git_branch}
- **Letzter Commit:** {git_last_commit}

Push mit: `cd {code_path} && git push`

## Deployment
- **Provider:** {deploy_provider}
- **URL:** {deploy_url}
- **Secrets liegen in:** {deploy_secrets}

Deployen mit: *(noch nicht konfiguriert — siehe `/vercel-deploy` o.ä.)*

## So sprichst du mit openclaude über dieses Projekt
Sag in deinem Voice/Prompt einen dieser Aliasse als Präfix, dann weiß openclaude wo gearbeitet wird:

{aliases_examples}

Beispiele:
- *„In {slug}: füge eine Funktion bar() in foo.py hinzu."*
- *„{slug}: was ist der letzte commit?"*
- *„Deploy {slug} auf vercel"*

## Notizen
*(hier kannst du frei reinschreiben — Architekturentscheidungen, ToDos, Lessons)*

---
*Manifest-Format v1 · auto-generiert durch `/project-bootstrap`*
