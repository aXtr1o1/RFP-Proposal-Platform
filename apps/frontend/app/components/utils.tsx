export const saveAllComments = async (
  supabase: any,
  uuid: string,
  commentsList: { comment1: string; comment2: string }[],

) => {
  try {
    // Convert the list of comments to a JSON string
    

    // Upsert into Supabase: update if uuid exists, insert if not
    const { data, error } = await supabase
      .from("proposal_comments")
      .upsert(
        {
          uuid,
          comments: commentsList,
        },
        { onConflict: ["uuid"] } // specify UUID as unique key
      );

    if (error) console.error("Error saving comments:", error);
    else console.log("Saved all comments:", data);
  } catch (err) {
    console.error("Failed to save comments:", err);
  }
};
