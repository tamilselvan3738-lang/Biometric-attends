from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from apps.attendance.models import AttendanceRecord
from apps.departments.models import Department
from apps.employee_management.models import EmployeeProfile
from apps.leave_management.models import LeaveRequest
from apps.accounts.permissions import admin_required, employee_required
from datetime import timedelta, datetime

@login_required
@admin_required
def attendance_report_view(request):
    """
    Detailed company-wide attendance reporting sheet with department and date range filters. Isolated by creator.
    """
    departments = Department.objects.all()
    records = AttendanceRecord.objects.filter(user__employeeprofile__created_by=request.user).select_related('user', 'user__employeeprofile', 'user__employeeprofile__department')
    
    # Apply Filters
    dept_id = request.GET.get('department')
    status = request.GET.get('status')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if dept_id:
        records = records.filter(user__employeeprofile__department_id=dept_id)
    if status:
        records = records.filter(status=status)
    if start_date:
        records = records.filter(date__gte=start_date)
    if end_date:
        records = records.filter(date__lte=end_date)
        
    # Load matching OvertimeRecords and join them
    from apps.attendance.models import OvertimeRecord
    ot_records = OvertimeRecord.objects.filter(user__employeeprofile__created_by=request.user)
    if start_date:
        ot_records = ot_records.filter(date__gte=start_date)
    if end_date:
        ot_records = ot_records.filter(date__lte=end_date)
    if dept_id:
        ot_records = ot_records.filter(user__employeeprofile__department_id=dept_id)

    ot_lookup = {(ot.user_id, ot.date): ot for ot in ot_records}
    for r in records:
        r.ot_record = ot_lookup.get((r.user_id, r.date))
        
    context = {
        'departments': departments,
        'records': records,
        'selected_dept': dept_id,
        'selected_status': status,
        'start_date': start_date,
        'end_date': end_date
    }
    return render(request, 'reports/attendance_report.html', context)

@login_required
@employee_required
def employee_report_view(request):
    """
    Allows individual employees to download personal monthly reports.
    """
    records = AttendanceRecord.objects.filter(user=request.user).select_related('user', 'user__employeeprofile')
    
    # Optional month filter
    month = request.GET.get('month')
    if month:
        # Expected format YYYY-MM
        try:
            parsed_date = datetime.strptime(month, "%Y-%m").date()
            records = records.filter(date__year=parsed_date.year, date__month=parsed_date.month)
        except ValueError:
            pass

    # Load matching OvertimeRecords and join them
    from apps.attendance.models import OvertimeRecord
    ot_records = OvertimeRecord.objects.filter(user=request.user)
    if month:
        try:
            parsed_date = datetime.strptime(month, "%Y-%m").date()
            ot_records = ot_records.filter(date__year=parsed_date.year, date__month=parsed_date.month)
        except ValueError:
            pass

    ot_lookup = {ot.date: ot for ot in ot_records}
    for r in records:
        r.ot_record = ot_lookup.get(r.date)
            
    total_days = records.count()
    present_days = records.filter(status='PRESENT').count()
    late_days = records.filter(status='LATE').count()
    half_days = records.filter(status='HALF_DAY').count()
    
    # Calculate total earned salary including OT pay for the filtered period
    total_earned = sum(
        float(r.calculated_salary) + (float(r.ot_record.calculated_amount) if r.ot_record else 0.0)
        for r in records
    )
    
    context = {
        'records': records,
        'total_days': total_days,
        'present_days': present_days,
        'late_days': late_days,
        'half_days': half_days,
        'total_earned': total_earned,
        'selected_month': month
    }
    return render(request, 'reports/employee_report.html', context)

@login_required
@admin_required
def analytics_view(request):
    """
    Renders analytical charts and percentage ratios for company attendance. Isolated by creator.
    """
    today = timezone.localdate()
    seven_days_ago = today - timedelta(days=7)
    
    total_staff = EmployeeProfile.objects.filter(status='ACTIVE', created_by=request.user).count()
    
    # Calculate ratios for the last 7 days
    recent_records = AttendanceRecord.objects.filter(date__gte=seven_days_ago, user__employeeprofile__created_by=request.user)
    
    total_possible_presences = total_staff * 7
    actual_presences = recent_records.filter(status__in=['PRESENT', 'LATE']).count()
    lateness_count = recent_records.filter(status='LATE').count()
    
    attendance_rate = round((actual_presences / total_possible_presences) * 100, 2) if total_possible_presences > 0 else 0.0
    lateness_rate = round((lateness_count / actual_presences) * 100, 2) if actual_presences > 0 else 0.0
    
    attendance_offset = round(251.32 * (1.0 - (attendance_rate / 100.0)), 2)
    lateness_offset = round(251.32 * (1.0 - (lateness_rate / 100.0)), 2)
    
    pending_leaves = LeaveRequest.objects.filter(status='PENDING').count()
    
    context = {
        'attendance_rate': attendance_rate,
        'lateness_rate': lateness_rate,
        'attendance_offset': attendance_offset,
        'lateness_offset': lateness_offset,
        'pending_leaves': pending_leaves,
        'total_staff': total_staff,
    }
    return render(request, 'reports/analytics.html', context)
