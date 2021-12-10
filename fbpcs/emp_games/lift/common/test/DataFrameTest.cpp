/*
 * Copyright (c) Facebook, Inc. and its affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#include <stdexcept>
#include <unordered_set>
#include <vector>

#include <gtest/gtest.h>

#include "fbpcs/emp_games/lift/common/Column.h"
#include "fbpcs/emp_games/lift/common/DataFrame.h"

using namespace df;

TEST(DataFrameTest, CreateBasicDataFrame) {
  DataFrame df;
  Column<int64_t> c1{1, 2, 3};
  df.get<int64_t>("intCol1") = c1;

  Column<int64_t> c2{4, 5, 6};
  df.get<int64_t>("intCol2") = std::move(c2);

  df.get<int64_t>("intCol3") = {7, 8, 9};

  df.get<std::string>("stringCol") = {"a", "b", "c"};
  df.get<std::vector<int64_t>>("intVecCol") = {{1, 2}, {3, 4}, {5, 6}};
}

TEST(DataFrameTest, MissingColumn) {
  DataFrame df;
  df.get<int64_t>("abc") = {1, 2, 3};
  // Throw because we're accessing a missing column
  EXPECT_THROW(df.at<int64_t>("def"), std::out_of_range);
  // Throw because we're accessing the wrong type
  EXPECT_THROW(df.at<std::string>("abc"), BadTypeException);
}

TEST(DataFrameTest, CheckType) {
  DataFrame::TypeInfo string{std::type_index(typeid(std::string)), "string"};
  DataFrame::TypeInfo int64{std::type_index(typeid(int64_t)), "int64_t"};
  DataFrame::TypeInfo string2{std::type_index(typeid(std::string)), "string"};

  EXPECT_NO_THROW(DataFrame::checkType(string, string2));
  EXPECT_THROW(DataFrame::checkType(string, int64), BadTypeException);
}

TEST(DataFrameTest, DropColumn) {
  DataFrame df;
  std::vector<int64_t> vI{1, 2, 3};
  std::vector<std::string> vS{"a", "b", "c"};

  df.get<int64_t>("intCol") = vI;
  Column cI(vI);
  df.get<std::string>("stringCol") = vS;
  Column cS(vS);

  EXPECT_EQ(df.at<int64_t>("intCol"), cI);
  EXPECT_EQ(df.at<std::string>("stringCol"), cS);

  df.drop<int64_t>("intCol");
  EXPECT_THROW(df.at<int64_t>("intCol"), std::out_of_range);
}

TEST(DataFrameDetail, Parse) {
  EXPECT_EQ(123, detail::parse<int64_t>("123"));
  EXPECT_THROW(detail::parse<int64_t>("abc"), ParseException);
}

TEST(DataFrameDetail, ParseVector) {
  std::vector<int64_t> expected{1, 2, 3};
  EXPECT_EQ(expected, detail::parseVector<int64_t>("[1,2,3]"));
  EXPECT_THROW(detail::parseVector<int64_t>("abc"), ParseException);
  // Missing trailing ']'
  EXPECT_THROW(detail::parseVector<int64_t>("["), ParseException);
  EXPECT_THROW(detail::parseVector<int64_t>("[1,2,3"), ParseException);
  // Missing both brackets
  EXPECT_THROW(detail::parseVector<int64_t>("1,2,3"), ParseException);
  // Not a vector
  EXPECT_THROW(detail::parseVector<int64_t>("1"), ParseException);
  // Empty string
  EXPECT_THROW(detail::parseVector<int64_t>(""), ParseException);
  // Empty vector
  std::vector<int64_t> expected2{};
  EXPECT_EQ(expected2, detail::parseVector<int64_t>("[]"));
}

TEST(DataFrameTest, Keys) {
  DataFrame df;
  df.get<std::string>("bool1") = {"true", "false"};
  df.get<std::string>("bool2") = {"1", "0"};
  df.get<std::string>("int1") = {"123", "111"};
  df.get<std::string>("int2") = {"456", "222"};
  df.get<std::string>("intVec") = {"[7,8,9]", "[333]"};

  std::unordered_set<std::string> allKeys{
      "bool1", "bool2", "int1", "int2", "intVec"};
  EXPECT_EQ(allKeys, df.keys());
  EXPECT_EQ(allKeys, df.keysOf<std::string>());

  DataFrame df2;
  df2.get<bool>("bool1") = {true, false};
  df2.get<bool>("bool2") = {true, false};
  df2.get<int64_t>("int1") = {123, 111};
  df2.get<int64_t>("int2") = {456, 222};
  df2.get<std::vector<int64_t>>("intVec") = {{7, 8, 9}, {333}};

  EXPECT_EQ(allKeys, df2.keys());

  std::unordered_set<std::string> boolKeys{"bool1", "bool2"};
  EXPECT_EQ(boolKeys, df2.keysOf<bool>());
}

TEST(DataFrameTest, ContainsKey) {
  DataFrame df;
  df.get<bool>("bool1") = {true, false};
  df.get<bool>("bool2") = {true, false};
  df.get<int64_t>("int1") = {123, 111};
  df.get<int64_t>("int2") = {456, 222};
  df.get<std::vector<int64_t>>("intVec") = {{7, 8, 9}, {333}};

  EXPECT_TRUE(df.containsKey("bool1"));
  EXPECT_TRUE(df.containsKey("int1"));
  EXPECT_TRUE(df.containsKey("intVec"));
  EXPECT_FALSE(df.containsKey("int9"));
}

TEST(DataFrameTest, LoadFromRowsBasic) {
  TypeMap t{
      .boolColumns = {},
      .intColumns = {},
      .intVecColumns = {},
  };

  std::vector<std::string> header = {
      "bool1", "bool2", "int1", "int2", "intVec"};
  std::vector<std::vector<std::string>> rows = {
      {"true", "1", "123", "456", "[7,8,9]"},
      {"false", "0", "111", "222", "[333]"},
  };

  DataFrame expected;
  expected.get<std::string>("bool1") = {"true", "false"};
  expected.get<std::string>("bool2") = {"1", "0"};
  expected.get<std::string>("int1") = {"123", "111"};
  expected.get<std::string>("int2") = {"456", "222"};
  expected.get<std::string>("intVec") = {"[7,8,9]", "[333]"};

  auto actual = DataFrame::loadFromRows(t, header, rows);
  EXPECT_EQ(expected.at<std::string>("bool1"), actual.at<std::string>("bool1"));
  EXPECT_EQ(expected.at<std::string>("bool2"), actual.at<std::string>("bool2"));
  EXPECT_EQ(expected.at<std::string>("int1"), actual.at<std::string>("int1"));
  EXPECT_EQ(expected.at<std::string>("int2"), actual.at<std::string>("int2"));
  EXPECT_EQ(
      expected.at<std::string>("intVec"), actual.at<std::string>("intVec"));
}

TEST(DataFrameTest, LoadFromRowsAdvanced) {
  TypeMap t{
      .boolColumns = {"bool1", "bool2"},
      .intColumns = {"int1", "int2"},
      .intVecColumns = {"intVec"},
  };

  std::vector<std::string> header = {
      "bool1", "bool2", "int1", "int2", "intVec"};
  std::vector<std::vector<std::string>> rows = {
      {"true", "1", "123", "456", "[7,8,9]"},
      {"false", "0", "111", "222", "[333]"},
  };

  DataFrame expected;
  expected.get<bool>("bool1") = {true, false};
  expected.get<bool>("bool2") = {true, false};
  expected.get<int64_t>("int1") = {123, 111};
  expected.get<int64_t>("int2") = {456, 222};
  expected.get<std::vector<int64_t>>("intVec") = {{7, 8, 9}, {333}};

  auto actual = DataFrame::loadFromRows(t, header, rows);
  EXPECT_EQ(expected.at<bool>("bool1"), actual.at<bool>("bool1"));
  EXPECT_EQ(expected.at<bool>("bool2"), actual.at<bool>("bool2"));
  EXPECT_EQ(expected.at<int64_t>("int1"), actual.at<int64_t>("int1"));
  EXPECT_EQ(expected.at<int64_t>("int2"), actual.at<int64_t>("int2"));
  EXPECT_EQ(
      expected.at<std::vector<int64_t>>("intVec"),
      actual.at<std::vector<int64_t>>("intVec"));
}
