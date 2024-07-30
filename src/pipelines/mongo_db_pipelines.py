def performance_by_standard_pipeline():
    return [
        {"$unwind": "$questions"},
        {"$group": {
            "_id": "$questions.standard",
            "avg_percent_correct": {"$avg": {"$toDouble": "$questions.percent_correct"}},
            "question_count": {"$sum": 1}
        }},
        {"$sort": {"avg_percent_correct": -1}}
    ]

def best_performing_standard_pipeline(n):
    pipeline = performance_by_standard_pipeline()
    pipeline.append({"$limit": n})
    return pipeline

def worst_performing_standard_pipeline(n):
    pipeline = performance_by_standard_pipeline()
    pipeline[-1] = {"$sort": {"avg_percent_correct": 1}}  # Change sort order
    pipeline.append({"$limit": n})
    return pipeline

def question_count_by_standard_pipeline():
    return [
        {"$unwind": "$questions"},
        {"$group": {
            "_id": "$questions.standard",
            "question_count": {"$sum": 1}
        }},
        {"$sort": {"question_count": -1}}
    ]


def most_missed_question_by_test_pipeline():
    return [
        {"$unwind": "$questions"},
        {"$match": {
            "questions.item_type_name": "Multiple Choice Question",
            "questions.correct_answer": {"$ne": ""},
            "questions.correct_answer": {"$ne": None}
        }},
        {"$lookup": {
            "from": "students",
            "let": {
                "test_id": "$test_id", 
                "question_id": "$questions.question_id",
                "correct_answer": "$questions.correct_answer"
            },
            "pipeline": [
                {"$unwind": "$test_results"},
                {"$unwind": "$test_results.responses"},
                {"$match": {
                    "$expr": {
                        "$and": [
                            {"$eq": ["$test_results.test_id", "$$test_id"]},
                            {"$eq": ["$test_results.responses.question", "$$question_id"]}
                        ]
                    }
                }},
                {"$project": {
                    "response": "$test_results.responses.response",
                    "answered": {"$ne": ["$test_results.responses.response", ""]},
                    "correct": {"$eq": ["$test_results.responses.response", "$$correct_answer"]}
                }}
            ],
            "as": "student_responses"
        }},
        {"$unwind": "$student_responses"},
        {"$group": {
            "_id": {
                "test_id": "$test_id",
                "question_id": "$questions.question_id"
            },
            "incorrect_count": {"$sum": {"$cond": [
                {"$and": [
                    "$student_responses.answered",
                    {"$eq": ["$student_responses.correct", False]}
                ]}, 
                1, 0
            ]}},
            "total_answered": {"$sum": {"$cond": ["$student_responses.answered", 1, 0]}},
            "total_count": {"$sum": 1}
        }},
        {"$project": {
            "test_id": "$_id.test_id",
            "question_id": "$_id.question_id",
            "incorrect_percentage": {
                "$cond": [
                    {"$eq": ["$total_answered", 0]},
                    0,
                    {"$multiply": [{"$divide": ["$incorrect_count", "$total_answered"]}, 100]}
                ]
            },
            "response_rate": {"$multiply": [{"$divide": ["$total_answered", "$total_count"]}, 100]}
        }},
        {"$sort": {"test_id": 1, "incorrect_percentage": -1}},
        {"$group": {
            "_id": "$test_id",
            "most_missed_question": {"$first": "$$ROOT"}
        }}
    ]


def student_progress_over_time_pipeline():
    return [
        {"$unwind": "$test_results"},
        {"$sort": {"student_id": 1, "test_results.date": 1}},
        {"$group": {
            "_id": "$student_id",
            "progress": {"$push": {
                "date": "$test_results.date",
                "score": "$test_results.overall_score"
            }},
            "first_name": {"$first": "$first_name"},
            "last_name": {"$first": "$last_name"}
        }}
    ]

def question_difficulty_by_type_pipeline():
    return [
        {"$unwind": "$questions"},
        {"$lookup": {
            "from": "students",
            "let": {"test_id": "$test_id", "question_id": "$questions.question_id"},
            "pipeline": [
                {"$unwind": "$test_results"},
                {"$unwind": "$test_results.responses"},
                {"$match": {
                    "$expr": {
                        "$and": [
                            {"$eq": ["$test_results.test_id", "$$test_id"]},
                            {"$eq": ["$test_results.responses.question", "$$question_id"]}
                        ]
                    }
                }},
                {"$project": {"score": "$test_results.responses.score"}}
            ],
            "as": "student_responses"
        }},
        {"$unwind": "$student_responses"},
        {"$group": {
            "_id": "$questions.item_type_name",
            "avg_score": {"$avg": "$student_responses.score"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"avg_score": 1}}
    ]

def concept_mastery_pipeline():
    return [
        {"$unwind": "$questions"},
        {"$lookup": {
            "from": "students",
            "let": {"test_id": "$test_id", "question_id": "$questions.question_id"},
            "pipeline": [
                {"$unwind": "$test_results"},
                {"$unwind": "$test_results.responses"},
                {"$match": {
                    "$expr": {
                        "$and": [
                            {"$eq": ["$test_results.test_id", "$$test_id"]},
                            {"$eq": ["$test_results.responses.question", "$$question_id"]}
                        ]
                    }
                }},
                {"$project": {"score": "$test_results.responses.score"}}
            ],
            "as": "student_responses"
        }},
        {"$unwind": "$student_responses"},
        {"$group": {
            "_id": "$questions.standard",
            "avg_score": {"$avg": "$student_responses.score"},
            "count": {"$sum": 1}
        }},
        {"$project": {
            "standard": "$_id",
            "avg_score": 1,
            "count": 1,
            "mastery_level": {
                "$switch": {
                    "branches": [
                        {"case": {"$gte": ["$avg_score", 0.9]}, "then": "Mastered"},
                        {"case": {"$gte": ["$avg_score", 0.7]}, "then": "Proficient"},
                        {"case": {"$gte": ["$avg_score", 0.5]}, "then": "Developing"},
                    ],
                    "default": "Needs Improvement"
                }
            }
        }},
        {"$sort": {"avg_score": -1}}
    ]



def peer_comparison_pipeline():
    return [
        {"$unwind": "$test_results"},
        {"$group": {
            "_id": {
                "student_id": "$student_id",
                "class": "$test_results.class"
            },
            "avg_score": {"$avg": "$test_results.overall_score"},
            "first_name": {"$first": "$first_name"},
            "last_name": {"$first": "$last_name"}
        }},
        {"$group": {
            "_id": "$_id.class",
            "students": {"$push": {
                "student_id": "$_id.student_id",
                "name": {"$concat": ["$first_name", " ", "$last_name"]},
                "score": "$avg_score"
            }},
            "class_avg": {"$avg": "$avg_score"}
        }},
        {"$unwind": "$students"},
        {"$project": {
            "class": "$_id",
            "student": "$students.name",
            "student_score": "$students.score",
            "class_avg": 1,
            "percentile": {
                "$multiply": [
                    {"$divide": [
                        {"$size": {"$filter": {
                            "input": "$students",
                            "as": "s",
                            "cond": {"$lt": ["$$s.score", "$students.score"]}
                        }}},
                        {"$size": "$students"}
                    ]},
                    100
                ]
            }
        }},
        {"$sort": {"class": 1, "student_score": -1}}
    ]


def student_performance_by_standard_pipeline():
    return [
        {"$unwind": "$test_results"},
        {"$unwind": "$test_results.responses"},
        {"$lookup": {
            "from": "tests",
            "let": {"test_id": "$test_results.test_id", "question_id": "$test_results.responses.question"},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$test_id", "$$test_id"]}}},
                {"$unwind": "$questions"},
                {"$match": {
                    "$expr": {
                        "$and": [
                            {"$eq": ["$questions.question_id", "$$question_id"]},
                            {"$eq": ["$questions.item_type_name", "Multiple Choice Question"]},
                            {"$ne": ["$questions.correct_answer", ""]},
                            {"$ne": ["$questions.correct_answer", None]}
                        ]
                    }
                }}
            ],
            "as": "question_info"
        }},
        {"$unwind": "$question_info"},
        {"$group": {
            "_id": {
                "student_id": "$student_id",
                "standard": "$question_info.questions.standard"
            },
            "correct_count": {"$sum": {"$cond": [{"$eq": ["$test_results.responses.response", "$question_info.questions.correct_answer"]}, 1, 0]}},
            "total_count": {"$sum": 1},
            "first_name": {"$first": "$first_name"},
            "last_name": {"$first": "$last_name"}
        }},
        {"$project": {
            "student_id": "$_id.student_id",
            "standard": "$_id.standard",
            "first_name": 1,
            "last_name": 1,
            "avg_performance": {
                "$cond": [
                    {"$eq": ["$total_count", 0]},
                    None,
                    {"$multiply": [{"$divide": ["$correct_count", "$total_count"]}, 100]}
                ]
            },
            "total_questions": "$total_count"
        }}
    ]
    
def comprehensive_test_analysis_pipeline(query=None):
    pipeline = []
    if query:
        pipeline.append({  "$match": query })

    pipeline.extend([
        {"$unwind": "$test_results"},
        {"$unwind": "$test_results.responses"},
        {"$lookup": {
            "from": "tests",
            "let": {"test_id": "$test_results.test_id", "question_id": "$test_results.responses.question"},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$test_id", "$$test_id"]}}},
                {"$unwind": "$questions"},
                {"$match": {
                    "$expr": {
                        "$and": [
                            {"$eq": ["$questions.question_id", "$$question_id"]},
                            {"$ne": ["$questions.correct_answer", ""]},
                            {"$ne": ["$questions.correct_answer", None]}
                        ]
                    }
                }}
            ],
            "as": "question_info"
        }},
        {"$unwind": "$question_info"},
        {"$project": {
            "student_id": 1,
            "first_name": 1,
            "last_name": 1,
            "test_id": "$test_results.test_id",
            "test_name": "$question_info.assessment_name",
            "class_name": "$question_info.class",
            "question_id": "$test_results.responses.question",
            "question_type": "$question_info.questions.item_type_name",  # Include question type
            "student_response": "$test_results.responses.response",
            "correct_answer": "$question_info.questions.correct_answer",
            "standard": "$question_info.questions.standard",
            "is_correct": {"$eq": ["$test_results.responses.response", "$question_info.questions.correct_answer"]}
        }}
    ])

    return pipeline
    
