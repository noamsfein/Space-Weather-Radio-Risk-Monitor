# Niki: OpenAI API setup

This is a one-time manual setup for Niki Naderzad (`nnaderzad`). It gives Niki
the same optional live-briefing capability as Noam while keeping each person's
API credential private. The Kafka replay, deterministic briefing, and automated
tests still work without an OpenAI key.

## 1. Accept the organization invitation

1. Open the invitation Noam sent to the email associated with your OpenAI
   Platform account.
2. Sign in at <https://platform.openai.com/> using that invited email.
3. Accept the invitation to the `MSDS` API organization.
4. Confirm that `MSDS` appears in the organization selector.
5. Tell Noam when this is complete. He must then confirm that you are a member
   of the `Space Weather Radio Risk` API project.

OpenAI requires a person to belong to the API organization before that person
can be added to one of its projects. This API access is separate from GitHub,
ChatGPT, and the course systems.

## 2. Confirm project access

1. Select the `MSDS` organization.
2. Select the `Space Weather Radio Risk` project from the project menu.
3. Open **API Keys**.

If the project is missing or you cannot create a key, stop and message Noam.
Do not use or request Noam's key. He should verify that you were added to the
project as a project `Member`.

## 3. Create your own project key

1. While `Space Weather Radio Risk` is selected, choose **Create new secret
   key**.
2. Name the key:

   ```text
   space-weather-niki-local
   ```

3. Copy the key when it is displayed and store it in a password manager.
4. Do not paste the key into GitHub, Slack, text messages, screenshots, project
   documentation, or this repository.

The key is Niki's credential for the shared project. Noam uses a separate key.

## 4. Create the private local environment file

From the repository root, run:

```bash
git switch main
git pull --ff-only
cp .env.example .env
```

Open the new `.env` file locally and use this template:

```dotenv
# Private local credential. Never commit or share this value.
OPENAI_API_KEY=paste_nikis_own_project_key_here

# Keep blank until AI-2 documents the exact shared model identifier.
OPENAI_MODEL=
```

Replace only `paste_nikis_own_project_key_here`. Do not add spaces around `=`.
Do not put the real key into `.env.example`; that committed file must remain
blank.

## 5. Verify that Git ignores the secret

Run:

```bash
git check-ignore -v .env
git status --short
```

Expected result:

- `git check-ignore` reports that `.gitignore` ignores `.env`.
- `.env` does not appear in `git status --short`.

Do not run `git add -f .env`. If `.env` appears in Git status, stop and message
Noam before committing anything.

## 6. Verify the no-key project path now

AI-2 will add the optional live call and its exact model later. Until then, you
can confirm the existing deterministic briefing path without exposing the key:

```bash
env -u OPENAI_API_KEY python -m src.briefing
```

This command requires an existing `outputs/alert.json`. It must write
`outputs/briefing.txt` without contacting OpenAI.

Do not test the live key by pasting it into a shell command saved in terminal
history. After AI-2 is merged, use the documented project command, which will
load the private `.env` file.

## Completion check

Niki should mark the checklist task complete only after all of these are true:

- [ ] Accepted the `MSDS` OpenAI API organization invitation.
- [ ] Can select the `Space Weather Radio Risk` project.
- [ ] Created `space-weather-niki-local` inside that project.
- [ ] Stored the key privately.
- [ ] Created a local `.env` from `.env.example`.
- [ ] Confirmed `.env` is ignored and absent from Git status.
- [ ] Did not share or commit the key.
- [ ] Messaged Noam that setup is complete.

References: [OpenAI project users](https://platform.openai.com/docs/api-reference/project-users),
[API authentication](https://platform.openai.com/docs/api-reference/authentication),
and the [OpenAI API quickstart](https://platform.openai.com/docs/quickstart).
