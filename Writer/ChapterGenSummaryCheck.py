import json

import Writer.LLMEditor
import Writer.PrintUtils
import Writer.Config


def LLMSummaryCheck(Interface, _Logger, _RefSummary: str, _Work: str):
    """
    Generates a summary of the work provided, and compares that to the reference summary, asking if they answered the prompt correctly.
    """

    # LLM Length Check - Firstly, check if the length of the response was at least 100 words.
    if len(_Work.split(" ")) < 100:
        _Logger.Log(
            "Previous response didn't meet the length requirement, so it probably tried to cheat around writing.",
            7,
        )
        return False, ""

    # Build Summariziation Langchain
    SummaryLangchain: list = []
    SummaryLangchain.append(
        Interface.BuildSystemQuery(
            f"You are a helpful AI Assistant. Answer the user's prompts to the best of your abilities."
        )
    )
    SummaryLangchain.append(
        Interface.BuildUserQuery(
            f"""
Please summarize the following chapter:

<CHAPTER>
{_Work}
</CHAPTER>

Do not include anything in your response except the summary.

"""
        )
    )
    SummaryLangchain = Interface.ChatAndStreamResponse(
        _Logger, SummaryLangchain, Writer.Config.CHAPTER_STAGE1_WRITER_MODEL
    )  # CHANGE THIS MODEL EVENTUALLY - BUT IT WORKS FOR NOW!!!
    WorkSummary: str = Interface.GetLastMessageText(SummaryLangchain)

    # Now Summarize The Outline
    SummaryLangchain:list = []
    SummaryLangchain.append(Interface.BuildSystemQuery(f"You are a helpful AI Assistant. Answer the user's prompts to the best of your abilities."))
    SummaryLangchain.append(Interface.BuildUserQuery(f"""
Please summarize the following chapter outline:

<OUTLINE>
{_RefSummary}
</OUTLINE>

Do not include anything in your response except the summary.

"""))
    SummaryLangchain = Interface.ChatAndStreamResponse(_Logger, SummaryLangchain, Writer.Config.CHAPTER_STAGE1_WRITER_MODEL) # CHANGE THIS MODEL EVENTUALLY - BUT IT WORKS FOR NOW!!!
    OutlineSummary:str = Interface.GetLastMessageText(SummaryLangchain)

    # Now, generate a comparison JSON value.
    ComparisonLangchain: list = []
    ComparisonLangchain.append(
        Interface.BuildSystemQuery(
            f"You are a helpful AI Assistant. Answer the user's prompts to the best of your abilities."
        )
    )
    ComparisonLangchain.append(
        Interface.BuildUserQuery(
            f"""
Please compare the provided summary of a chapter and the associated outline, and indicate if the provided content roughly follows the outline.

Please write a JSON formatted response with no other content with the following keys.
Note that a computer is parsing this JSON so it must be correct.

<CHAPTER_SUMMARY>
{WorkSummary}
</CHAPTER_SUMMARY>

<OUTLINE>
{OutlineSummary}
</OUTLINE>

Please respond with the following JSON fields:

{{
"Suggestions": str
"DidFollowOutline": true/false
}}

Suggestions should include a string containing detailed markdown formatted feedback that will be used to prompt the writer on the next iteration of generation.
Specify general things that would help the writer remember what to do in the next iteration.
It will not see the current chapter, so feedback specific to this one is not helpful, instead specify areas where it needs to pay attention to either the prompt or outline.
The writer is also not aware of each iteration - so provide detailed information in the prompt that will help guide it.
Start your suggestions with 'Important things to keep in mind as you write: \n'.

It's okay if the summary isn't a complete perfect match, but it should have roughly the same plot, and pacing.

Again, remember to make your response JSON formatted with no extra words. It will be fed directly to a JSON parser.
"""
        )
    )
    ComparisonLangchain = Interface.ChatAndStreamResponse(
        _Logger, ComparisonLangchain, Writer.Config.REVISION_MODEL, _Format="json"
    )  # CHANGE THIS MODEL EVENTUALLY - BUT IT WORKS FOR NOW!!!

    Iters: int = 0
    while True:

        RawResponse = Interface.GetLastMessageText(ComparisonLangchain)
        RawResponse = RawResponse.replace("`", "")
        RawResponse = RawResponse.replace("json", "")

        try:
            Iters += 1
            Dict = json.loads(RawResponse)
            return (
                Dict["DidFollowOutline"],
                "### Extra Suggestions:\n" + Dict["Suggestions"],
            )
        except Exception as E:
            if Iters > 4:
                _Logger.Log("Critical Error Parsing JSON", 7)
                return False, ""

            _Logger.Log("Error Parsing JSON Written By LLM, Asking For Edits", 7)
            EditPrompt: str = (
                f"Please revise your JSON. It encountered the following error during parsing: {E}. Remember that your entire response is plugged directly into a JSON parser, so don't write **anything** except pure json."
            )
            ComparisonLangchain.append(Interface.BuildUserQuery(EditPrompt))
            _Logger.Log("Asking LLM TO Revise", 7)
            ComparisonLangchain = Interface.ChatAndStreamResponse(
                _Logger, ComparisonLangchain, Writer.Config.CHECKER_MODEL, _Format="json"
            )
            _Logger.Log("Done Asking LLM TO Revise JSON", 6)