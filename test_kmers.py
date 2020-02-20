# import pandas as pd

# df = pd.read_csv("test_neo1.list.tsv", sep="\t", comment="#")

# for i, group_df in df.groupby(by=["Chromosome", "Pos", "Ref", "Alt", "Mutation_type", "VAF", "Transcript_ID"]):
#     print(group_df)
#     if "V" in list(group_df["Mutation_type"]):
#         sequences = [sequence for sequence in group_df["Neoepitope"]]
#         print(sorted(sequences))
#         s_list = [sequences[0]]
#         to_pop = 0
#         while len(sequences) > 20:
#             sequences.pop(to_pop)
#             print(sequences)
#             for j, s in enumerate(sequences):
#                 new_i = False
#                 for i, si in enumerate(s_list):
#                     if si.startswith(s[1:]):
#                         new_i = i
#                     elif si.endswith(s[:-1]):
#                         new_i = i + 1
#                 if new_i != False:
#                     print(new_i)
#                     # s_list = [*s_list[:new_i], s ,*s_list[new_i:]]
#                     s_list.insert(new_i, s)
#                     to_pop = new_i
#                     break
#         print(s_list)
#         for i, seq in enumerate(s_list):
#             print(" "*i, seq)
#         exit()
