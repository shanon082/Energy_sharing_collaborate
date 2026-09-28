const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

export const getErrorMessage = (response: unknown): string => {
  if (!response) {
    return "Unknown error occurred";
  }

  if (response instanceof Error) {
    return formatErrorMessage(response.message);
  }

  if (typeof response === "string") {
    return formatErrorMessage(response);
  }

  if (isRecord(response)) {
    const message = response.message;
    if (Array.isArray(message) && typeof message[0] === "string") {
      return formatErrorMessage(message[0]);
    }
    if (typeof message === "string") {
      return formatErrorMessage(message);
    }
  }

  return "Unknown error occurred";
};

const formatErrorMessage = (message: string) => {
  return message.charAt(0).toUpperCase() + message.slice(1);
};
