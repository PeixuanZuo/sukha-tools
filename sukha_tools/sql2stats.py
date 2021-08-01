
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

# ROCm rpd_tracer
#connection.execute('''
#    insert into ops_with_launch_time
#        select 
#            rocpd_api_ops.id, 
#            rocpd_api.start, 
#            rocpd_op.start, 
#            rocpd_op.end-rocpd_op.start, 
#            B.string as op_type,
#            case when length(A.string) > 0 then A.string else B.string end as description,
#            "misc" as category
#        from rocpd_api_ops 
#            inner join rocpd_api on rocpd_api_ops.api_id = rocpd_api.id 
#            inner join rocpd_op on rocpd_api_ops.op_id = rocpd_op.id 
#            inner join rocpd_string A on A.id = rocpd_op.description_id 
#            inner join rocpd_string B ON B.id = rocpd_op.opType_id''')

# CUDA nsys sqlite
connection.execute('''
    insert into ops_with_launch_time
        select
            kernels.start as op_id, 
            runtime.start as api_start,
            kernels.start as op_start,
            kernels.end-kernels.start as duration, 
            "KernelExecution" as op_type,
            strings.value as description,
            "misc" as category
        from CUPTI_ACTIVITY_KIND_KERNEL as kernels 
            inner join StringIds as strings on strings.id == kernels.demangledName 
            inner join CUPTI_ACTIVITY_KIND_RUNTIME as runtime on kernels.correlationId = runtime.correlationId
    ''')


connection.execute('''
    create temporary table MemcpyOperationStrings (id INTEGER PRIMARY KEY, name TEXT)
    ''')

connection.execute('''
    insert into MemcpyOperationStrings (id, name) values
        (0, '[CUDA memcpy Unknown]'), (1, '[CUDA memcpy HtoD]'),
        (2, '[CUDA memcpy DtoH]'), (3, '[CUDA memcpy HtoA]'),
        (4, '[CUDA memcpy AtoH]'), (5, '[CUDA memcpy AtoA]'),
        (6, '[CUDA memcpy AtoD]'), (7, '[CUDA memcpy DtoA]'),
        (8, '[CUDA memcpy DtoD]'), (9, '[CUDA memcpy HtoH]'),
        (10, '[CUDA memcpy PtoP]'), (11, '[CUDA Unified Memory memcpy HtoD]'),
        (12, '[CUDA Unified Memory memcpy DtoH]'),
        (13, '[CUDA Unified Memory memcpy DtoD]'); 
    ''')

connection.execute('''
    insert into ops_with_launch_time
        select
            kernels.start as op_id, 
            runtime.start as api_start,
            kernels.start as op_start,
            kernels.end-kernels.start as duration, 
            "MemCpy" as op_type,
            strings.name as description,
            "misc" as category
        from CUPTI_ACTIVITY_KIND_MEMCPY as kernels 
            inner join MemcpyOperationStrings strings on strings.id == kernels.copyKind 
            inner join CUPTI_ACTIVITY_KIND_RUNTIME as runtime on kernels.correlationId = runtime.correlationId
    ''')

connection.execute('''
    insert into ops_with_launch_time
        select
            kernels.start as op_id, 
            runtime.start as api_start,
            kernels.start as op_start,
            kernels.end-kernels.start as duration, 
            "MemSet" as op_type,
            "[CUDA memset]" as description,
            "misc" as category
        from CUPTI_ACTIVITY_KIND_MEMSET as kernels 
            inner join StringIds as strings on strings.id == kernels.memKind 
            inner join CUPTI_ACTIVITY_KIND_RUNTIME as runtime on kernels.correlationId = runtime.correlationId
    ''')


# find the requested user ranges
# ROCM rpd_tracer
# connection.execute('''
#     create temporary table user_ranges as
#         select start, end, args from api 
#         where apiName == "UserMarker" and args like "{}"'''.format(args.range_like))

# CUDA nsys sqlite
connection.execute('''
    create temporary table user_ranges as 
        select start, end, text from NVTX_EVENTS
        where text like "{}"'''.format(args.range_like))


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
#    order by count(op_id) desc
#    ''')
#
#import csv
#with open("{}{}.csv".format(args.input_rpd[:-3], args.range_like), "w", newline='') as csv_file: 
#    csv_writer = csv.writer(csv_file)
#    csv_writer.writerow([i[0] for i in cursor.description])
#    csv_writer.writerows(cursor)
#
