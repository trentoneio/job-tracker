# Session -1 — Initial Architecture Brief (verbatim)

> Captured verbatim from the original project request on 2026-07-08.
> This session's role: architecture definition only — no code was written as a result.
> Build sessions begin at `session-0.md` (see `PLAN.md` §11).

---

This session is to define architecture only. Do not write any code as a result of this session. Your only job is to help define the architecture for an upcoming project of mine. 

I would like to create a webapp to help to track job applications. 

The app should take input from a user and organize the data in a helpful dashboard.

A user should be able to input information such as but not limited to the company that the job was for, the job title, the application's reference number, the date that the job was applied to, the full application when possible (in PDF format), the resume used for the application (in PDF format), a link to the job posting, and the current status of the application (which may change over time from different states such as received, ghosted, rejected, accepted, interviewed, etc)

The input over time should create a dashboard of useful information that will help the user keep track of all of their applications and their status' in one place. 

The dashboard, for example, could show the user all of their applications that they are still waiting on a reply on in one place. It could also have a Sankey diagram tracking the flow of application status'. Maybe also a pi chart showing application status.

It would also be neat if there was some sort of filter option that would let you change the output of the entire dashboard to only display information from ,for example, a single company.

All data should be easily exportable to some local downloadable format, such as a csv

This webapp will be hosted from a raspberry pi, but it will be built on windows, so it needs to support both (WSL). I want it to be accessible to any device on my local network. You can choose to host this in whatever format you like. Though, I am mostly familiar with docker.

Of course, since this will be creating a living record, I would like the data provided to the app to persist. That way, if the app suffers a crash, or power goes out, etc, the application can be restarted and all of the data doesn't need to be re-imported. For this, you can assume that the project will live in a single project directory containing the project's source as well as the current running project.

Make sure that the whole project is captured in a git repo that follows some set of standards. All commits should have a "type" field at the end of the commit that documents the commit type (documentation, new feature, bug fix, etc.)

Your job is to do the following:
1. Create and initialize the git repo that will host this project. I want the project to be in "C:\Users\Trenton\coding-projects" (or /mnt/c/Users/Trenton/coding-projects from a WSL environment).
2. Create directory in the repo for future session prompts. Put this prompt into the directory. You can consider yourself as session -1
3. Create a plan to make this project a reality. Make a PLAN.md in the repo.
