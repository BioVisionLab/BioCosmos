async function isBackendAlive(): Promise<boolean> {
  try {
    const response = await fetch(`/api/status`);
    if (!response.ok) {
      console.error(`Backend status check failed. Status: ${response.status}`);
      return false;
    }
    const data = await response.json();
    return data.status === "ok";
  } catch (error) {
    console.error("Error checking backend status:", error);
    return false;
  }
}

export { isBackendAlive };
