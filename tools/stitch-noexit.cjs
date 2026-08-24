/**
 * Keeps the Stitch CLI's JSON output flushable when it runs non-interactively.
 *
 * The script contains no credentials.  Authentication stays in the local
 * STITCH_API_KEY environment variable managed by the developer workstation.
 */
process.exit = (code = 0) => {
  process.exitCode = code;
};
