# from collections import defaultdict

# l = [('chr19', 17807975, 'AG', '', 'D', 0.132, 'NA', 'NA', 0, 'ENST00000318683.7'),
#     ('chr19', 17807981, 'GG', '', 'D', 0.105, 'NA', 'NA', 0, 'ENST00000318683.7'),
#     ('chr19', 17807975, 'AG', '', 'D', 0.132, 'NA', 'NA', 0, 'ENST00000595387.1'),
#     ('chr19', 17807981, 'GG', '', 'D', 0.105, 'NA', 'NA', 0, 'ENST00000595387.1')]

# for m in set(mutation[0:7] for mutation in l):
#     print(m)

# mutation_dict = defaultdict(list)
# for mut in l:
#     mutation_dict[(mut[0:7])+(mut[8],)].append([mut[7], mut[9]])
# print(mutation_dict)
