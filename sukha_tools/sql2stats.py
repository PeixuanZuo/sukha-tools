
import sqlite3
import argparse

parser = argparse.ArgumentParser(description='collect operators within roctxrange')
parser.add_argument('input_rpd', type=str, help="input rpd db")
parser.add_argument('range_like', type=str, help="roctx range queried with sql like")
args = parser.parse_args()


connection = sqlite3.connect(args.input_rpd)

# fill table linking GPU operations to its API invocation
connection.execute('''
    create temporary table ops_with_launch_time (
        op_id int, 
        api_start int, 
        op_start int, 
        duration int, 
        op_type varchar(256),
        description varchar(2048), 
        category varchar(256) 
        )''')

connection.execute('''
    insert into ops_with_launch_time
        select 
            rocpd_api_ops.id, 
            rocpd_api.start, 
            rocpd_op.start, 
            rocpd_op.end-rocpd_op.start, 
            B.string as op_type,
            case when length(A.string) > 0 then A.string else B.string end as description,
            "misc" as category
        from rocpd_api_ops 
            inner join rocpd_api on rocpd_api_ops.api_id = rocpd_api.id 
            inner join rocpd_op on rocpd_api_ops.op_id = rocpd_op.id 
            inner join rocpd_string A on A.id = rocpd_op.description_id 
            inner join rocpd_string B ON B.id = rocpd_op.opType_id''')

# find the requested user ranges
connection.execute('''
    create temporary table user_ranges as
        select start, end, args from api 
        where apiName == "UserMarker" and args like "{}"'''.format(args.range_like))


# pull the GPU operations within range into table
connection.execute('''
    create temporary table ops_in_user_range (
        op_id int,
        user_range varchar(256),
        op_duration double,
        op_type varchar(256),
        op_description varchar(2048)
        )''')

for start, end, user_range in connection.execute('select * from user_ranges'):
    print(start, end, user_range)
    connection.execute('''
        insert into ops_in_user_range 
            select op_id, "{}", duration, op_type, description 
            from ops_with_launch_time 
            where api_start between {} and {}
            order by op_start'''.format(user_range, start, end))

# export statistics in user range
cursor = connection.cursor()
cursor.execute('''
    select count(op_id), sum(op_duration)/1.e6, "{}"
    from ops_in_user_range
    order by count(op_id) desc
    '''.format(args.range_like))

print(cursor.fetchall())

## export statistics in user range
#cursor = connection.cursor()
#cursor.execute('''
#    select count(op_id), sum(op_duration), op_type, op_description
#    from ops_in_user_range
#    group by op_description
#    order by sum(op_duration) desc
#    ''')
#
#import csv
#with open("{}{}.csv".format(args.input_rpd[:-3], args.range_like), "w", newline='') as csv_file: 
#    csv_writer = csv.writer(csv_file)
#    csv_writer.writerow([i[0] for i in cursor.description])
#    csv_writer.writerows(cursor)
#
