Read and update tracking doc at .ralph/IMPROVEMENTS.md. 
Read and reference docs/spec.md. At critical design decision points, review docs/spec.md to ensure it is up to date with general guidance that have sharpened, evolved, or added. 
Run the code and iterate. 

- Review and address user feedback. 
- Address critical value improvements. 
- Ensure it runs with expected behavior. 
- Verify the outputs and the agent trajectory (this should be stored per run for post-run analysis here and in aggregate later) with 2 parallel but distinct reviewer subagents, one to review the quality of the final digest, one to review the quality of the agent decisions and tool actions.

  **Reviewer calibration**: Reviewers must be demanding. Surface at least 3-5 concrete improvement ideas per review. Ask: "What would make this 2x more useful?" Consider: depth of analysis, insight density, actionability, citation quality, cross-referencing, missed connections, and whether the output justifies the compute spent. If a digest entry could be written by reading just the source URL title, it's too shallow. 
- Improvements should be tracked during this build loop in a file for design on the next loop iteration. 

When the tracked capability improvement ideas are all low value for effort/complexity/runtime costs, run the skill for simplifying the code with no behavior change. 
