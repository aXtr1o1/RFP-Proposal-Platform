type JsonPrimitive = string | number | boolean | null;
type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };

export const saveAllComments = async (
  supabase: any,
  uuid: string,
  commentsList: { comment1: string; comment2: string }[],
) => {
  try {
    const { data, error } = await supabase
      .from("proposal_comments")
      .upsert(
        {
          uuid,
          comments: commentsList,
        },
        { onConflict: ["uuid"] },
      );

    if (error) console.error("Error saving comments:", error);
    else console.log("Saved all comments:", data);
  } catch (err) {
    console.error("Failed to save comments:", err);
  }
};

export const safeJsonParse = <T extends JsonValue | Record<string, unknown> | unknown>(
  input: string | null | undefined,
  fallback: T,
): T => {
  if (!input) {
    return fallback;
  }

  try {
    return JSON.parse(input) as T;
  } catch (error) {
    console.warn("safeJsonParse: failed to parse JSON value", error);
    return fallback;
  }
};
