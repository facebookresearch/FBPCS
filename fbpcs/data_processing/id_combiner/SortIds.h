/*
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#pragma once

#include <filesystem>
#include <istream>
#include <ostream>
#include <string>
#include <unordered_map>
#include <vector>

namespace pid::combiner {
/*
This file implements the sortIds that is used to sort data files based on id
in order to return a sorted file

For example, if for  index 'id', specified columsn are val1 and val 2
and this input file content:
id        val1       val2        val3
2           z         [c]         v3
3           q         [l]         v4
1           x       [a,b,c]       v1


The output would be a sorted list based on the id key:
id        val1       val2        val3
1           x       [a,b,c]       v1
2           z         [c]         v3
3           q         [l]         v4
*/
void sortIds(std::istream& inFilePath, std::ostream& outFilePath);
} // namespace pid::combiner
