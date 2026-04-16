
export async function invoke(command, payload) {
  return globalThis.__fluxioTestInvoke(command, payload);
}
